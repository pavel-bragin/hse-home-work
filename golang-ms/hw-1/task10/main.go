package main

import "fmt"

func main() {
	var n int
	fmt.Print("Введите количество чисел N: ")
	if _, err := fmt.Scan(&n); err != nil || n < 1 {
		fmt.Println("Ошибка: N должно быть целым числом больше 0")
		return
	}

	sum := 0
	var maxNum, minNum int
	even, odd := 0, 0

	for i := 1; i <= n; i++ {
		var x int
		fmt.Printf("Введите число %d: ", i)
		if _, err := fmt.Scan(&x); err != nil {
			fmt.Println("Ошибка: нужно ввести целое число")
			return
		}

		sum += x
		if i == 1 || x > maxNum {
			maxNum = x
		}
		if i == 1 || x < minNum {
			minNum = x
		}
		if x%2 == 0 {
			even++
		} else {
			odd++
		}
	}

	avg := float64(sum) / float64(n)

	fmt.Println("Сумма:", sum)
	fmt.Printf("Среднее значение: %.2f\n", avg)
	fmt.Println("Максимальное значение:", maxNum)
	fmt.Println("Минимальное значение:", minNum)
	fmt.Println("Количество чётных:", even)
	fmt.Println("Количество нечётных:", odd)
}
