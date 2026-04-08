#include <stdio.h>
#include <math.h>

int main() {
    float a = 0.1f;
    float b = 0.2f;
    float c = a + b;

    printf("a: %f\n", a);
    printf("b: %f\n", b);
    printf("a + b: %f\n", c);

    float d = a * b;
    printf("a * b: %f\n", d);
    
    return 0;
}