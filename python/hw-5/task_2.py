from task_1 import Account
from datetime import datetime


class CheckingAccount(Account):
    account_type = "Расчётный счёт"
    
    # Инициализация расчетного счета через Account с нулевым балансом
    def __init__(self, account_holder, balance=0):
        super().__init__(account_holder, balance)


class SavingsAccount(Account):
    account_type = "Сберегательный счёт"
    
    # Инициализация сберегательного счета через Account с нулевым балансом
    def __init__(self, account_holder, balance=0):
        super().__init__(account_holder, balance)
    
    def apply_interest(self, rate):
        if rate < 0:
            raise ValueError("Процентная ставка не может быть отрицательной")
        
        interest_amount = self._balance * (rate / 100)
        self._balance += interest_amount
        self.operations_history.append({
            'type': 'interest',
            'amount': interest_amount,
            'datetime': datetime.now(),
            'balance_after': self._balance,
            'status': 'success'
        })
    
    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        
        # максимальная сумма снятия - 50% от баланса
        max_withdraw = self._balance * 0.5
        
        if amount > max_withdraw:
            # если сумма снятия больше максимальной суммы снятия, то операция не выполняется
            self.operations_history.append({
                'type': 'withdraw',
                'amount': amount,
                'datetime': datetime.now(),
                'balance_after': self._balance,
                'status': 'fail'
            })
        elif self._balance >= amount:
            # если сумма снятия меньше или равна балансу, то операция выполняется
            self._balance -= amount
            self.operations_history.append({
                'type': 'withdraw',
                'amount': amount,
                'datetime': datetime.now(),
                'balance_after': self._balance,
                'status': 'success'
            })
        else:
            # если сумма снятия больше баланса, то операция не выполняется
            self.operations_history.append({
                'type': 'withdraw',
                'amount': amount,
                'datetime': datetime.now(),
                'balance_after': self._balance,
                'status': 'fail'
            })


if __name__ == "__main__":
    print("=== Тестирование CheckingAccount ===")
    checking = CheckingAccount("Петр Петров", 5000)
    print(f"Тип счёта: {CheckingAccount.account_type}")
    print(f"Номер счёта: {checking.account_number}")
    print(f"Баланс: {checking.get_balance()}")
    
    checking.deposit(2000)
    checking.withdraw(1500)
    checking.withdraw(3000)
    print(f"Баланс после операций: {checking.get_balance()}")
    print()
    
    print("=== Тестирование SavingsAccount ===")
    savings = SavingsAccount("Мария Сидорова", 10000)
    print(f"Тип счёта: {SavingsAccount.account_type}")
    print(f"Номер счёта: {savings.account_number}")
    print(f"Начальный баланс: {savings.get_balance()}")
    
    savings.apply_interest(7)
    print(f"Баланс после начисления 7%: {savings.get_balance()}")
    
    savings.deposit(3000)
    print(f"Баланс после пополнения: {savings.get_balance()}")
    
    print("\nПопытка снять 8000 (более 50% от баланса):")
    savings.withdraw(8000)
    print(f"Баланс: {savings.get_balance()}")
    
    print("\nПопытка снять 3000 (менее 50% от баланса):")
    savings.withdraw(3000)
    print(f"Баланс: {savings.get_balance()}")
    print()
    
    print("=== Крупнейшие операции ===")
    largest = savings.get_largest_operations(3)
    for i, op in enumerate(largest, 1):
        print(f"{i}. {op['type']}: {op['amount']:.2f}, статус: {op['status']}, дата: {op['datetime']}")
    print()
    
    print("=== Тест валидации имени ===")
    try:
        invalid_account = CheckingAccount("павел брагин", 1000)
    except ValueError as e:
        print(f"Ошибка: {e}")
    
    try:
        invalid_account = CheckingAccount("Павел228", 1000)
    except ValueError as e:
        print(f"Ошибка: {e}")
    
    print("\n=== Тест отрицательных сумм ===")
    try:
        savings.deposit(-1337)
    except ValueError as e:
        print(f"Ошибка при пополнении: {e}")
    
    try:
        savings.withdraw(-1337)
    except ValueError as e:
        print(f"Ошибка при снятии: {e}")

