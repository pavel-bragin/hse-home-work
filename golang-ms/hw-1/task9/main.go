package main

import "fmt"

func main() {
	var balance float64
	fmt.Print("Введите баланс: ")
	if _, err := fmt.Scan(&balance); err != nil || balance < 0 {
		fmt.Println("Ошибка: баланс должен быть числом не меньше 0")
		return
	}

	for {
		fmt.Println()
		fmt.Println("1. Посмотреть баланс")
		fmt.Println("2. Пополнить баланс")
		fmt.Println("3. Снять средства")
		fmt.Println("0. Выход")
		fmt.Print("Выберите действие: ")

		var choice int
		if _, err := fmt.Scan(&choice); err != nil {
			fmt.Println("Ошибка ввода")
			return
		}

		switch choice {
		case 1:
			fmt.Printf("Ваш баланс: %.2f\n", balance)
		case 2:
			var amount float64
			fmt.Print("Сумма пополнения: ")
			fmt.Scan(&amount)
			if amount <= 0 {
				fmt.Println("Сумма должна быть больше 0")
			} else {
				balance += amount
				fmt.Printf("Баланс пополнен, теперь на счёте %.2f\n", balance)
			}
		case 3:
			var amount float64
			fmt.Print("Сумма снятия: ")
			fmt.Scan(&amount)
			if amount <= 0 {
				fmt.Println("Сумма должна быть больше 0")
			} else if amount > balance {
				fmt.Printf("Недостаточно средств, на счёте %.2f\n", balance)
			} else {
				balance -= amount
				fmt.Printf("Выдано %.2f, остаток %.2f\n", amount, balance)
			}
		case 0:
			fmt.Println("До свидания!")
			return
		default:
			fmt.Println("Нет такого действия")
		}
	}
}
