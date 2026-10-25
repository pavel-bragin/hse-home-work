package main

import "fmt"

func main() {
	var n int
	fmt.Print("Сколько будет чисел? ")
	if _, err := fmt.Scan(&n); err != nil || n < 1 {
		fmt.Println("Ошибка: количество должно быть целым числом больше 0")
		return
	}

	var maxNum, minNum float64
	for i := 1; i <= n; i++ {
		var x float64
		fmt.Printf("Введите число %d: ", i)
		if _, err := fmt.Scan(&x); err != nil {
			fmt.Println("Ошибка: нужно ввести число")
			return
		}

		if i == 1 || x > maxNum {
			maxNum = x
		}
		if i == 1 || x < minNum {
			minNum = x
		}
	}

	fmt.Println("Максимальное значение:", maxNum)
	fmt.Println("Минимальное значение:", minNum)
}
