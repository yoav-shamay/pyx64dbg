#include <stdio.h>
#include <stdlib.h>

#define mod 998244353

int main()
{
    setvbuf(stdout, NULL, _IONBF, 0); // Disable buffering for stdout
    printf("Enter password: ");
    long long number;
    scanf("%d", &number);
    for (int i = 0; i < 100; i++)
    {
        number *= 17;
        number += 31;
        number %= mod;
    }
    if (number == 0x1337)
    {
        printf("Correct!\n");
    }
    else
    {
        printf("Wrong!\n");
    }
}