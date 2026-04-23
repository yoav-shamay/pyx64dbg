#include <stdio.h>
#include <math.h>

int main() {
    float f_a, f_b, f_c;
    double d_a, d_b, d_c;
    long double ld_a, ld_b, ld_c;
    scanf("%f %f", &f_a, &f_b);
    scanf("%lf %lf", &d_a, &d_b);
    scanf("%Lf %Lf", &ld_a, &ld_b);
    f_c = f_a + f_b;
    d_c = d_a + d_b;
    ld_c = ld_a + ld_b;
    printf("float: %.25f + %.25f = %.25f\n", f_a, f_b, f_c);
    printf("double: %.25lf + %.25lf = %.25lf\n", d_a, d_b, d_c);
    printf("long double: %.25Lf + %.25Lf = %.25Lf\n", ld_a, ld_b, ld_c);
    return 0;
}