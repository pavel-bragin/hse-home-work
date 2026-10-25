package main

import "fmt"

func main() {
	var n int
	fmt.Print("Введите количество чисел N: ")
	if _, err := fmt.Scan(&n); err != nil || n < 1 {
		fmt.Println("Ошибка: N должно быть целым числом больше 0")
		return
	}

	positive, negative, zeros := 0, 0, 0
	for i := 1; i <= n; i++ {
		var x float64
		fmt.Printf("Введите число %d: ", i)
		if _, err := fmt.Scan(&x); err != nil {
			fmt.Println("Ошибка: нужно ввести число")
			return
		}

		if x > 0 {
			positive++
		} else if x < 0 {
			negative++
		} else {
			zeros++
		}
	}

	fmt.Println("Положительных:", positive)
	fmt.Println("Отрицательных:", negative)
	fmt.Println("Нулей:", zeros)
}
