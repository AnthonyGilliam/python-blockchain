from hashlib import sha256
import time
start_time = time.time()

x = 'Hello World'
y = 0
difficulty = 4

def create_hash(x, y):
    return sha256(f'{x*y}'.encode()).hexdigest()

# Keep incrementing until the last 4 digits ends with 0000
while (create_hash(x, y))[:difficulty] != "0" * difficulty:
    y += 1
    print(create_hash(x, y))


print (f'The solution for y = {y} and hash is: {create_hash(x, y)}')
print("*#$*#$( %s seconds )*#$*#$" % (time.time() - start_time))
