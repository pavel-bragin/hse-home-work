from task_2 import CheckingAccount, SavingsAccount
import csv
import json
from datetime import datetime


def load_from_csv(account, filename):
    """
    Загрузка истории операций из CSV файла
    Args:
        account: объект класса CheckingAccount или SavingsAccount
        filename: имя файла CSV
    Returns:
        None
    """
    transactions = []
    with open(filename, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['account_number'] == account.account_number:
                transactions.append(row)
    
    cleaned_transactions = account.clean_history(transactions)
    account.load_history(cleaned_transactions)


def load_from_json(account, filename):
    """
    Загрузка истории операций из JSON файла
    Args:
        account: объект класса CheckingAccount или SavingsAccount
        filename: имя файла JSON
    Returns:
        None
    """
    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    transactions = [t for t in data if t['account_number'] == account.account_number]
    cleaned_transactions = account.clean_history(transactions)
    account.load_history(cleaned_transactions)


class CheckingAccountExtended(CheckingAccount):
    """
    Расширенный класс CheckingAccount для загрузки истории операций из CSV и JSON
    """
    def clean_history(self, transactions):
        """
        Очистка истории операций
        Args:
            transactions: список операций, валидные только deposit и withdraw
        Returns:
            список очищенных операций
        """
        cleaned = []
        valid_operations = ['deposit', 'withdraw']
        
        for trans in transactions:
            if not self._is_valid_transaction(trans, valid_operations):
                continue
            cleaned.append(trans)
        
        return cleaned
    
    def _is_valid_transaction(self, trans, valid_operations):
        if not trans.get('operation') or trans['operation'] not in valid_operations:
            return False
        
        if not trans.get('amount'):
            return False
        
        try:
            amount = float(trans['amount'])
            if amount <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        if not trans.get('balance_after'):
            return False
        
        try:
            float(trans['balance_after'])
        except (ValueError, TypeError):
            return False
        
        if not trans.get('status') or trans['status'] not in ['success', 'fail']:
            return False
        
        if not self._is_valid_date(trans.get('date', '')):
            return False
        
        return True
    
    def _is_valid_date(self, date_str):
        """
        Проверка даты на валидность
        Args:
            date_str: строка с датой в формате YYYY-MM-DD HH:MM:SS, YYYY-MM-DD, DD/MM/YYYY HH:MM, DD/MM/YYYY
        Returns:
            True, если дата валидна, False в противном случае
        """
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except (ValueError, TypeError):
                continue
        return False
    
    def load_history(self, transactions):
        """
        Загрузка истории операций
        Args:
            transactions: список операций
        Returns:
            None
        """
        self._balance = 0 # начальный баланс
        self.operations_history = [] # история операций
        
        for trans in transactions:
            operation_type = trans['operation'] # тип операции
            amount = float(trans['amount']) # сумма операции, приводится к float
            balance_after = float(trans['balance_after']) # баланс после операции, приводится к float
            status = trans['status'] # статус операции
            
            date_str = trans['date'] # дата операции
            date_obj = self._parse_date(date_str) # дата операции, приводится к datetime
            
            self.operations_history.append({
                'type': operation_type,
                'amount': amount,
                'datetime': date_obj,
                'balance_after': balance_after,
                'status': status
            })
            
            if status == 'success':
                self._balance = balance_after
    
    def _parse_date(self, date_str):
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return datetime.now()


class SavingsAccountExtended(SavingsAccount):
    
    def clean_history(self, transactions):
        cleaned = []
        valid_operations = ['deposit', 'withdraw', 'interest']
        
        for trans in transactions:
            if not self._is_valid_transaction(trans, valid_operations):
                continue
            cleaned.append(trans)
        
        return cleaned
    
    def _is_valid_transaction(self, trans, valid_operations):
        if not trans.get('operation') or trans['operation'] not in valid_operations:
            return False
        
        if not trans.get('amount'):
            return False
        
        try:
            amount = float(trans['amount'])
            if amount <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        if not trans.get('balance_after'):
            return False
        
        try:
            float(trans['balance_after'])
        except (ValueError, TypeError):
            return False
        
        if not trans.get('status') or trans['status'] not in ['success', 'fail']:
            return False
        
        if not self._is_valid_date(trans.get('date', '')):
            return False
        
        return True
    
    def _is_valid_date(self, date_str):
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except (ValueError, TypeError):
                continue
        return False
    
    def load_history(self, transactions):
        self._balance = 0
        self.operations_history = []
        
        for trans in transactions:
            operation_type = trans['operation']
            amount = float(trans['amount'])
            balance_after = float(trans['balance_after'])
            status = trans['status']
            
            date_str = trans['date']
            date_obj = self._parse_date(date_str)
            
            self.operations_history.append({
                'type': operation_type,
                'amount': amount,
                'datetime': date_obj,
                'balance_after': balance_after,
                'status': status
            })
            
            if status == 'success':
                self._balance = balance_after
    
    def _parse_date(self, date_str):
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return datetime.now()


if __name__ == "__main__":
    print("=== Тестирование загрузки из CSV ===")
    checking = CheckingAccountExtended("Павел Брагин")
    checking.account_number = "ACC-100001"
    
    print(f"Счёт: {checking.account_number}")
    print(f"Баланс до загрузки: {checking.get_balance()}")
    
    load_from_csv(checking, 'transactions_dirty.csv')
    
    print(f"Баланс после загрузки: {checking.get_balance()}")
    print(f"Количество операций в истории: {len(checking.get_history())}")
    
    print("\nПервые 3 операции:")
    for i, op in enumerate(checking.get_history()[:3], 1):
        print(f"{i}. {op['type']}: {op['amount']}, баланс: {op['balance_after']}, дата: {op['datetime']}")
    
    print("\n=== Тестирование загрузки из JSON ===")
    savings = SavingsAccountExtended("Мария Сидорова")
    savings.account_number = "ACC-100002"
    
    print(f"Счёт: {savings.account_number}")
    print(f"Баланс до загрузки: {savings.get_balance()}")
    
    load_from_json(savings, 'transactions_dirty.json')
    
    print(f"Баланс после загрузки: {savings.get_balance()}")
    print(f"Количество операций в истории: {len(savings.get_history())}")
    
    print("\nПервые 3 операции:")
    for i, op in enumerate(savings.get_history()[:3], 1):
        print(f"{i}. {op['type']}: {op['amount']}, баланс: {op['balance_after']}, дата: {op['datetime']}")
    
    print("\n=== Проверка фильтрации операций ===")
    print(f"Типы операций для CheckingAccount:")
    operation_types_checking = set(op['type'] for op in checking.get_history())
    print(f"  {operation_types_checking}")
    print(f"  Есть 'interest': {'interest' in operation_types_checking}")
    
    print(f"\nТипы операций для SavingsAccount:")
    operation_types_savings = set(op['type'] for op in savings.get_history())
    print(f"  {operation_types_savings}")
    print(f"  Есть 'interest': {'interest' in operation_types_savings}")

