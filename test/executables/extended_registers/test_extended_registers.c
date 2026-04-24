#include <stdio.h>

// 1. Force the compiler to target AVX2 (256-bit)
#pragma GCC target("avx2")
// 2. Enable high-level optimization
#pragma GCC optimize("O3")

int main()
{
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