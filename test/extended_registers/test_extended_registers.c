#include <stdio.h>

// 1. Force the compiler to target AVX2 (256-bit)
#pragma GCC target("avx2")
// 2. Enable high-level optimization
#pragma GCC optimize("O3")

void print_int128(__int128 value)
{
    if (value < 0)
    {
        putchar('-');
        value = -value;
    }
    char buffer[40]; // enough to hold 2^128 in decimal
    int i = 39;
    buffer[i] = '\0';
    do
    {
        i--;
        buffer[i] = '0' + (value % 10);
        value /= 10;
    } while (value > 0);
    printf("%s\n", &buffer[i]);
}

int main()
{
    // int128
    __int128 a, b, c;
    scanf("%20[0-9]", &a);
    scanf("%20[0-9]", &b);
    c = a + b;
    print_int128(c);

    // vectorization
    int arr_1[8], arr_2[8], arr_3[8];
    for (int i = 0; i < 8; i++)
    {
        scanf("%d", &arr_1[i]);
    }
    for (int i = 0; i < 8; i++)
    {
        scanf("%d", &arr_2[i]);
    }
    for (int i = 0; i < 8; i++)
    {
        arr_3[i] = arr_1[i] + arr_2[i];
    }
    for (int i = 0; i < 8; i++)
    {
        printf("%d ", arr_3[i]);
    }
    printf("\n");
    return 0;
}