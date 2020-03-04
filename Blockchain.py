import hashlib
import json

from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

from flaskrun import flaskrun


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.currentTransactions = []
        self.nodes = set()  # Set of nodes - only unique values are stored - idempotent.

        # create genesis block.
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        """
        Add a new node to the list of nodes.
        :param address: <str> address of the node eg: http://192.168.0.10:5005
        :return: None
        """

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL with path '192.168.0.0:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def deregister_node(self, address):
        """
        remove the nodes from the list.
        :param address: <str> address of the node eg: http://192.168.0.10:5005
        :return: None
        """

        if len(self.nodes) == 0:
            return

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.remove(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL with path '192.168.0.0:5000'.
            self.nodes.remove(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid. Consensus - longest valid chain is authoritative.

        :param chain: <list> a blockchain
        :return: <bool> True if valid, False if not.
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'lastBlock: {last_block}')
            print(f'currentBlock: {block}')
            print("\n\n--------------------\n")
            # Check that the hash of the block is correct
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False

            # Check if the proof of work is valid.
            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts by replacing our chain with the longest chain
        in the network

        :return: <bool> True if the chain is replaced, False if not.
        """

        neighbors = self.nodes
        new_chain = None

        # We're looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all nodes on the network
        for node in neighbors:
            print(f'requesting for node: {node}')
            response = requests.get(f'http://{node}/chain')
            print(f'node {node} - chain: {response}')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and is valid.
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if the length is longer and valid.
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        Create a new block in the blockchain.

        :param proof: <int> The proof given by the proof of the work algorithm
        :param previous_hash: (Optional) <str> Hash of the previous block.
        :return: new block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.currentTransactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        # Reset the current list of transactions
        self.currentTransactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined block.
        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount: <int> amount
        :return: <int> index of the block that holds the transaction
        """
        self.currentTransactions.append({
            'sender': sender,
            'recipient' : recipient,
            'amount' : amount,
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        # Returns the last block in the chain.
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a block.

        :param block: <dict> block
        :return: <str> hash of the block.
        """

        # Make sure the dictionary is Ordered, otherwise we will have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_block):
        """
        Simple proof of work algorithm
        - find a number 'p' such that hash(pp') contains last 4 leading zeroes, where p is the previous p'
        - p is the previous proof, and p' is the new proof
        :param last_block: last block
        :return: <int>
        """

        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        Validates the Proof: Does hash(last_proof, proof) contains 4 leading zeroes?

        :param last_proof: <int> Previous proof
        :param proof: <int> current proof
        :param last_hash: <str> The hash of the previous block
        :return:<bool> True if correct, false if not
        """
        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# Instantiates our node.
app = Flask(__name__)

# Generates a globally unique address for this node.
node_identifier = str(uuid4()).replace('-', '')

# Instantiate our blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # We will run the proof of work algorithm to get the next proof..
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)

    # We must receive a reward for finding the proof.
    # The sender is "0" to signify that this node has mined a new coin.
    blockchain.new_transaction(
        sender = "0",
        recipient=node_identifier,
        amount=1,
    )

    # Forge the new block by adding it to the chain.
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': 'New block forged',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods = ['POST'])
def new_transactions():
    values = request.get_json()

    # Check that the required fields are in the POSTed data
    required = ['sender', 'recipient', 'amount']
    if not all (k in values for k in required):
        return 'Missing values: {k}', 400

    # Create a new transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes', methods=['GET'])
def all_nodes():
    response = {
        'message': 'All registered nodes',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error, please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/deRegister', methods=['POST'])
def deregister_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error, please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.deregister_node(node)

    response = {
        'message': 'Nodes de-registered',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods = ['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain got replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000)
    # Usage: py blockchain.py --port 5000
    # app = Flask(__name__)
    flaskrun(app)