#include <stdio.h>

// make sure error not repeated for every function
int f(void) {
}

int main(void) {
	int c;
	c = getchar();
	while (c != 10) {
		putchar(c);
		c = getchar();
	}
	int d = getchar();
	if (d >= 65 && d <= 90) {
		printf("upper case\b");
	}
}
