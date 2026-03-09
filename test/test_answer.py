result = 0x1337
mod = 998244353
iterations = 100

num = result
for i in range(iterations):
    num = (num - 31 + mod) % mod
    num = (num * pow(17, -1, mod)) % mod

print(num)
#687113069