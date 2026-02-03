# SecureBank - Technical Documentation

## 📚 Complete Project Documentation

This document provides in-depth technical details about the SecureBank application, including architecture, implementation details, and advanced usage.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Installation Guide](#installation-guide)
3. [Feature Documentation](#feature-documentation)
4. [Database Design](#database-design)
5. [Code Structure](#code-structure)
6. [API Reference](#api-reference)
7. [Testing Guide](#testing-guide)
8. [Troubleshooting](#troubleshooting)

---

## System Architecture

### Three-Layer Architecture

SecureBank follows a clean three-layer architecture pattern:

```
┌─────────────────────────────────────┐
│     Presentation Layer (GUI)        │
│  - LoginFrame                       │
│  - RegisterFrame                    │
│  - DashboardFrame                   │
│  - TransactionHistoryFrame          │
│  - TransferFrame                    │
│  - AccountDetailsFrame              │
└─────────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────────┐
│    Business Logic Layer             │
│  - BankController                   │
│    • Authentication                 │
│    • Transaction Processing         │
│    • Validation                     │
└─────────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────────┐
│    Data Access Layer                │
│  - DatabaseManager                  │
│    • CRUD Operations                │
│    • Transaction Logging            │
│    • Data Persistence               │
└─────────────────────────────────────┘
              ↓ ↑
┌─────────────────────────────────────┐
│         SQLite Database             │
│  - users table                      │
│  - transactions table               │
└─────────────────────────────────────┘
```

### Design Patterns Used

1. **MVC Pattern** - Separation of concerns between UI, logic, and data
2. **Singleton Pattern** - Single database connection instance
3. **Factory Pattern** - Frame creation and switching
4. **Repository Pattern** - DatabaseManager abstracts data access

---

## Installation Guide

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 7/macOS 10.12/Linux | Windows 10/macOS 12/Ubuntu 20.04 |
| Python | 3.8 | 3.10+ |
| RAM | 2 GB | 4 GB |
| Storage | 50 MB | 100 MB |
| Display | 1024x768 | 1920x1080 |

### Detailed Installation Steps

#### Windows

```powershell
# 1. Install Python (if not installed)
# Download from https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation

# 2. Verify Python installation
python --version

# 3. Clone repository
git clone https://github.com/codedbyamankanojiya/Bank-Management.git
cd Bank-Management

# 4. Create virtual environment
python -m venv venv

# 5. Activate virtual environment
.\venv\Scripts\activate

# 6. Install dependencies
pip install customtkinter

# 7. Run application
python bankapp.py
```

#### macOS/Linux

# 1. Verify Python installation
python3 --version

# 2. Clone repository
git clone https://github.com/codedbyamankanojiya/Bank-Management.git
cd Bank-Management

# 3. Create virtual environment
python3 -m venv venv

# 4. Activate virtual environment
source venv/bin/activate

# 5. Install dependencies
pip install customtkinter

# 6. Run application
python bankapp.py
```

### Dependency Details

```
customtkinter==5.2.1
├── darkdetect
└── packaging
```

---

## Feature Documentation

### 1. User Registration

**Purpose:** Create new bank accounts with unique identifiers

**Process Flow:**
1. User clicks "Create New Account" on login screen
2. System displays registration form
3. User enters full name and 4-digit PIN
4. System validates input:
   - Name must not be empty
   - PIN must be exactly 4 digits
   - PIN must contain only numbers
5. System generates unique 10-digit account number
6. Account created in database with initial balance of ₹0
7. Success message displays account number
8. User redirected to login screen

**Validation Rules:**
- Name: Required, any characters allowed
- PIN: Required, exactly 4 digits, numeric only

**Database Impact:**
- New row inserted into `users` table
- `created_at` timestamp automatically set

---

### 2. User Authentication

**Purpose:** Secure login to existing accounts

**Process Flow:**
1. User enters account number and PIN
2. System validates input fields are not empty
3. System queries database for account number
4. If account exists, PIN is compared
5. On successful match:
   - User session created
   - User data loaded into memory
   - Dashboard displayed
6. On failure:
   - Error message shown
   - User remains on login screen

**Security Measures:**
- PIN stored as plain text (consider hashing for production)
- No account enumeration (same error for invalid account/PIN)
- Session management prevents unauthorized access

---

### 3. Deposit Money

**Purpose:** Add funds to user account

**Process Flow:**
1. User enters amount in deposit field
2. Click "Deposit" button
3. System validates:
   - Amount is not empty
   - Amount is numeric
   - Amount is positive (> 0)
4. Current balance retrieved from session
5. New balance calculated (current + deposit)
6. Database updated with new balance
7. Transaction logged with type "DEPOSIT"
8. UI refreshed to show new balance
9. Success message displayed
10. Input field cleared

**Transaction Record:**
```python
{
    "user_id": <user_id>,
    "type": "DEPOSIT",
    "amount": <amount>,
    "recipient_account": None,
    "description": "Deposit",
    "timestamp": <current_timestamp>
}
```

---

### 4. Withdraw Money

**Purpose:** Remove funds from user account

**Process Flow:**
1. User enters amount in withdraw field
2. Click "Withdraw" button
3. System validates:
   - Amount is not empty
   - Amount is numeric
   - Amount is positive (> 0)
   - Current balance >= withdrawal amount
4. If insufficient balance:
   - Error message displayed
   - Transaction cancelled
5. If sufficient:
   - New balance calculated (current - withdrawal)
   - Database updated
   - Transaction logged with type "WITHDRAW"
   - UI refreshed
   - Success message displayed

**Error Handling:**
- Insufficient balance: "Insufficient Balance"
- Invalid amount: "Invalid amount"
- Empty field: "Please enter amount"

---

### 5. Money Transfer

**Purpose:** Send money between accounts

**Process Flow:**
1. User navigates to Transfer screen
2. Enters recipient account number
3. Enters transfer amount
4. Click "Transfer Now"
5. System validates:
   - Both fields not empty
   - Amount is numeric and positive
   - Recipient account exists
   - Recipient ≠ sender (no self-transfer)
   - Sender has sufficient balance
6. Database transaction begins:
   - Sender balance decreased
   - Recipient balance increased
   - Two transaction records created:
     - TRANSFER_OUT for sender
     - TRANSFER_IN for recipient
7. If any step fails, entire transaction rolled back
8. Success message displayed
9. Fields cleared

**Transaction Records:**

Sender:
```python
{
    "user_id": <sender_id>,
    "type": "TRANSFER_OUT",
    "amount": <amount>,
    "recipient_account": <recipient_account>,
    "description": "Transfer to <recipient_name>",
    "timestamp": <current_timestamp>
}
```

Recipient:
```python
{
    "user_id": <recipient_id>,
    "type": "TRANSFER_IN",
    "amount": <amount>,
    "recipient_account": <sender_account>,
    "description": "Transfer from <sender_name>",
    "timestamp": <current_timestamp>
}
```

---

### 6. Transaction History

**Purpose:** View all account transactions

**Process Flow:**
1. User clicks "Transaction History" from dashboard
2. System queries database for all user transactions
3. Results ordered by timestamp (newest first)
4. Limited to 50 most recent transactions
5. Each transaction displayed in card format:
   - Icon based on type
   - Transaction type and description
   - Timestamp
   - Amount with color coding

**Display Rules:**
- Green (+) for: DEPOSIT, TRANSFER_IN
- Red (-) for: WITHDRAW, TRANSFER_OUT
- Icons: 💵 Deposit, 💸 Withdraw, 📤 Transfer Out, 📥 Transfer In

---

### 7. Account Details

**Purpose:** Display complete account information

**Information Shown:**
- Account holder name
- Account number (10 digits)
- Current balance (formatted with commas)
- Account creation date and time

**Data Source:**
- Retrieved from current user session
- Real-time balance from database

---

## Database Design

### Schema Diagram

```
┌─────────────────────────────────────┐
│            users                    │
├─────────────────────────────────────┤
│ id (PK)          INTEGER            │
│ name             TEXT                │
│ pin              TEXT                │
│ account_number   TEXT (UNIQUE)      │
│ balance          INTEGER             │
│ created_at       TIMESTAMP           │
└─────────────────────────────────────┘
              │
              │ 1:N
              ↓
┌─────────────────────────────────────┐
│         transactions                │
├─────────────────────────────────────┤
│ id (PK)          INTEGER            │
│ user_id (FK)     INTEGER            │
│ type             TEXT                │
│ amount           INTEGER             │
│ recipient_account TEXT               │
│ timestamp        TIMESTAMP           │
│ description      TEXT                │
└─────────────────────────────────────┘
```

### Table Specifications

#### users Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique user identifier |
| name | TEXT | NOT NULL | Full name of account holder |
| pin | TEXT | NOT NULL | 4-digit authentication PIN |
| account_number | TEXT | UNIQUE, NOT NULL | 10-digit account number |
| balance | INTEGER | DEFAULT 0 | Current account balance in rupees |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Account creation date/time |

#### transactions Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique transaction identifier |
| user_id | INTEGER | FOREIGN KEY → users(id) | Reference to user |
| type | TEXT | NOT NULL | Transaction type (DEPOSIT/WITHDRAW/TRANSFER_OUT/TRANSFER_IN) |
| amount | INTEGER | NOT NULL | Transaction amount in rupees |
| recipient_account | TEXT | NULL | Recipient account for transfers |
| timestamp | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Transaction date/time |
| description | TEXT | NULL | Transaction description |

### Indexes

```sql
-- Automatically created
CREATE INDEX idx_users_account_number ON users(account_number);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
```

---

## Code Structure

### Class Hierarchy

```
BankApp (CTk)
    └── controller: BankController
        └── db: DatabaseManager
            └── conn: sqlite3.Connection

Frames (CTkFrame)
    ├── LoginFrame
    ├── RegisterFrame
    ├── DashboardFrame
    ├── TransactionHistoryFrame
    ├── TransferFrame
    └── AccountDetailsFrame
```

### Key Methods

#### DatabaseManager

```python
create_tables()              # Initialize database schema
create_user(name, pin, acc_no, balance=0)  # Create new user
get_user_by_account(acc_no)  # Retrieve user by account number
update_balance(acc_no, new_balance)  # Update user balance
add_transaction(user_id, type, amount, recipient, desc)  # Log transaction
get_transaction_history(user_id, limit=50)  # Retrieve transactions
transfer_money(from_acc, to_acc, amount)  # Execute transfer
close()                      # Close database connection
```

#### BankController

```python
sign_up(name, pin)           # Register new user
sign_in(acc_no, pin)         # Authenticate user
deposit(amount)              # Process deposit
withdraw(amount)             # Process withdrawal
transfer(recipient, amount)  # Process transfer
get_transaction_history(limit=50)  # Get user transactions
get_account_info()           # Get current user info
get_balance()                # Get current balance
logout()                     # Clear user session
```

---

## API Reference

### DatabaseManager API

#### `create_user(name: str, pin: str, account_number: str, balance: int = 0) -> bool`

Creates a new user account.

**Parameters:**
- `name` (str): Full name of the account holder
- `pin` (str): 4-digit PIN for authentication
- `account_number` (str): Unique 10-digit account number
- `balance` (int, optional): Initial balance, defaults to 0

**Returns:**
db = DatabaseManager()
success = db.create_user("Salman Khan", "1234", "1234567890", 0)

Transfers money between two accounts.

**Parameters:**
- `from_account` (str): Sender's account number
- `to_account` (str): Recipient's account number
- `amount` (int): Amount to transfer

**Returns:**
- `tuple[bool, str]`: (Success status, Message)

**Possible Returns:**
- `(True, "Transfer successful")`
- `(False, "Account not found")`
- `(False, "Insufficient balance")`
- `(False, <error_message>)`

**Example:**
```python
success, message = db.transfer_money("1234567890", "0987654321", 1000)
if success:
    print("Transfer completed!")
```

---

## Testing Guide

### Manual Testing Checklist

#### Registration Tests
- [ ] Create account with valid name and PIN
- [ ] Try empty name (should fail)
- [ ] Try 3-digit PIN (should fail)
- [ ] Try 5-digit PIN (should fail)
- [ ] Try non-numeric PIN (should fail)
- [ ] Verify account number is displayed
- [ ] Verify redirect to login screen

#### Login Tests
- [ ] Login with valid credentials
- [ ] Try invalid account number (should fail)
- [ ] Try invalid PIN (should fail)
- [ ] Try empty fields (should fail)
- [ ] Verify dashboard loads on success

#### Deposit Tests
- [ ] Deposit positive amount
- [ ] Try negative amount (should fail)
- [ ] Try zero amount (should fail)
- [ ] Try non-numeric input (should fail)
- [ ] Verify balance updates
- [ ] Verify transaction logged

#### Withdrawal Tests
- [ ] Withdraw amount less than balance
- [ ] Try withdrawing more than balance (should fail)
- [ ] Try negative amount (should fail)
- [ ] Verify balance updates
- [ ] Verify transaction logged

#### Transfer Tests
- [ ] Transfer to valid account
- [ ] Try transferring to own account (should fail)
- [ ] Try invalid recipient account (should fail)
- [ ] Try amount exceeding balance (should fail)
- [ ] Verify both balances update
- [ ] Verify both transaction records created

---

## Troubleshooting

### Common Issues

#### Issue: Application won't start

**Symptoms:** Error message when running `python bankapp.py`

**Solutions:**
1. Verify Python version: `python --version` (must be 3.8+)
2. Check CustomTkinter installation: `pip list | grep customtkinter`
3. Reinstall dependencies: `pip install --upgrade customtkinter`
4. Check for syntax errors: `python -m py_compile bankapp.py`

---

#### Issue: Database locked error

**Symptoms:** `sqlite3.OperationalError: database is locked`

**Solutions:**
1. Close all instances of the application
2. Delete `bank.db` file (WARNING: This deletes all data)
3. Restart the application
4. Ensure only one instance is running

---

#### Issue: Transactions not showing

**Symptoms:** Transaction history is empty despite making transactions

**Solutions:**
1. Check if transactions are being logged:
   ```python
   # Add debug print in add_transaction method
   print(f"Logging transaction: {trans_type}, {amount}")
   ```
2. Verify database connection is active
3. Check transaction query in `get_transaction_history()`

---

#### Issue: Balance not updating

**Symptoms:** Balance remains same after deposit/withdrawal

**Solutions:**
1. Verify `update_balance()` is being called
2. Check database commit: `self.conn.commit()`
3. Ensure `refresh_balance()` is called in UI
4. Check session data is being updated

---

### Debug Mode

To enable debug output, add this at the start of `bankapp.py`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Performance Optimization

### Database Optimization

1. **Indexes:** Already implemented on frequently queried columns
2. **Connection Pooling:** Consider for multi-user scenarios
3. **Batch Operations:** Group multiple updates when possible

### UI Optimization

1. **Lazy Loading:** Transaction history loads on demand
2. **Pagination:** Limit to 50 transactions (configurable)
3. **Caching:** User session data cached in memory

---

## Security Considerations

### Current Implementation

✅ PIN-based authentication  
✅ Input validation  
✅ SQL injection prevention (parameterized queries)  
✅ Balance verification before transactions  

### Recommended Enhancements

⚠️ **PIN Hashing:** Store hashed PINs instead of plain text
```python
import hashlib
hashed_pin = hashlib.sha256(pin.encode()).hexdigest()
```

⚠️ **Session Timeout:** Implement automatic logout after inactivity

⚠️ **Rate Limiting:** Prevent brute force attacks on login

⚠️ **Encryption:** Encrypt sensitive data in database

---

## Deployment

### Standalone Executable

Create executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name SecureBank bankapp.py
```

Executable will be in `dist/` folder.

---

## Maintenance

### Regular Tasks

- **Backup Database:** Copy `bank.db` regularly
- **Update Dependencies:** `pip install --upgrade customtkinter`
- **Monitor Logs:** Check for errors and unusual activity
- **Test Features:** Verify all operations work correctly

---

## Support & Contact

For technical support or questions:
- GitHub Issues: https://github.com/codedbyamankanojiya/Bank-Management/issues
- Documentation: This file

---

**Last Updated:** February 2026  
**Version:** 1.0  
**Author:** Aman Kanojiya
