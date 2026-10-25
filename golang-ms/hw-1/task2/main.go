package main

import "fmt"

func main() {
	var n int
	fmt.Print("Введите число N: ")
	if _, err := fmt.Scan(&n); err != nil {
		fmt.Println("Ошибка: нужно ввести целое число")
		return
	}

	if n > 0 {
		fmt.Println("Число положительное")
	} else if n < 0 {
		fmt.Println("Число отрицательное")
	} else {
		fmt.Println("Число равно нулю")
	}

	if n%2 == 0 {
		fmt.Println("Число чётное")
	} else {
		fmt.Println("Число нечётное")
	}

	if n%3 == 0 && n%5 == 0 {
		fmt.Println("Делится и на 3, и на 5")
	} else if n%3 == 0 {
		fmt.Println("Делится на 3, но не делится на 5")
	} else if n%5 == 0 {
		fmt.Println("Делится на 5, но не делится на 3")
	} else {
		fmt.Println("Не делится ни на 3, ни на 5")
	}
}
