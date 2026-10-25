package main

import "fmt"

func main() {
	var a, b float64
	var op string

	fmt.Print("Введите первое число: ")
	if _, err := fmt.Scan(&a); err != nil {
		fmt.Println("Ошибка: нужно ввести число")
		return
	}
	fmt.Print("Введите операцию (+, -, *, /): ")
	fmt.Scan(&op)
	fmt.Print("Введите второе число: ")
	if _, err := fmt.Scan(&b); err != nil {
		fmt.Println("Ошибка: нужно ввести число")
		return
	}

	var result float64
	switch op {
	case "+":
		result = a + b
	case "-":
		result = a - b
	case "*":
		result = a * b
	case "/":
		if b == 0 {
			fmt.Println("Ошибка: деление на ноль невозможно")
			return
		}
		result = a / b
	default:
		fmt.Println("Неизвестная операция:", op)
		return
	}

	fmt.Printf("%g %s %g = %g\n", a, op, b, result)
}
