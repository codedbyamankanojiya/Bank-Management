import sqlite3
import random
import os

class DatabaseManager:
    def __init__(self, db_name="bank.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Users table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pin TEXT NOT NULL,
                account_number TEXT UNIQUE NOT NULL,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transactions table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                recipient_account TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        self.conn.commit()

    def create_user(self, name, pin, account_number, balance=0):
        try:
            self.cursor.execute("INSERT INTO users (name, pin, account_number, balance) VALUES (?, ?, ?, ?)",
                                (name, pin, account_number, balance))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_by_account(self, account_number):
        self.cursor.execute("SELECT * FROM users WHERE account_number = ?", (account_number,))
        return self.cursor.fetchone()

    def update_balance(self, account_number, new_balance):
        self.cursor.execute("UPDATE users SET balance = ? WHERE account_number = ?", (new_balance, account_number))
        self.conn.commit()

    def add_transaction(self, user_id, trans_type, amount, recipient_account=None, description=None):
        self.cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, recipient_account, description)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, trans_type, amount, recipient_account, description))
        self.conn.commit()

    def get_transaction_history(self, user_id, limit=50):
        self.cursor.execute("""
            SELECT type, amount, recipient_account, timestamp, description
            FROM transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        return self.cursor.fetchall()

    def transfer_money(self, from_account, to_account, amount):
        """Transfer money between two accounts"""
        try:
            # Get both users
            sender = self.get_user_by_account(from_account)
            recipient = self.get_user_by_account(to_account)
            
            if not sender or not recipient:
                return False, "Account not found"
            
            if sender[4] < amount:  # balance is at index 4
                return False, "Insufficient balance"
            
            # Update balances
            new_sender_balance = sender[4] - amount
            new_recipient_balance = recipient[4] + amount
            
            self.update_balance(from_account, new_sender_balance)
            self.update_balance(to_account, new_recipient_balance)
            
            # Log transactions for both users
            self.add_transaction(sender[0], "TRANSFER_OUT", amount, to_account, f"Transfer to {recipient[1]}")
            self.add_transaction(recipient[0], "TRANSFER_IN", amount, from_account, f"Transfer from {sender[1]}")
            
            return True, "Transfer successful"
        except Exception as e:
            self.conn.rollback()
            return False, str(e)

    def close(self):
        self.conn.close()

class BankController:
    def __init__(self):
        self.db = DatabaseManager()
        self.current_user = None

    def sign_up(self, name, pin):
        if not name or len(pin) != 4 or not pin.isdigit():
            return "Invalid Input. Pin must be 4 digits."
        
        account_number = str(random.randint(1000000000, 9999999999))
        if self.db.create_user(name, pin, account_number):
            return f"Account Created! Your Account Number is {account_number}"
        else:
            return "Error creating account. Try again."

    def sign_in(self, account_number, pin):
        user = self.db.get_user_by_account(account_number)
        if user:
            # user tuple: (id, name, pin, account_number, balance, created_at)
            if user[2] == pin:
                self.current_user = {
                    "id": user[0],
                    "name": user[1],
                    "account_number": user[3],
                    "balance": user[4],
                    "created_at": user[5] if len(user) > 5 else None
                }
                return True, f"Welcome {user[1]}"
            else:
                return False, "Incorrect PIN"
        return False, "Account not found"

    def deposit(self, amount):
        if not self.current_user:
            return False, "Not logged in"
        try:
            amount = int(amount)
            if amount <= 0:
                return False, "Amount must be positive"
            
            new_balance = self.current_user["balance"] + amount
            self.db.update_balance(self.current_user["account_number"], new_balance)
            self.current_user["balance"] = new_balance
            
            # Log transaction
            self.db.add_transaction(self.current_user["id"], "DEPOSIT", amount, description="Deposit")
            
            return True, f"Deposited ₹{amount}. New Balance: ₹{new_balance}"
        except ValueError:
            return False, "Invalid amount"

    def withdraw(self, amount):
        if not self.current_user:
            return False, "Not logged in"
        try:
            amount = int(amount)
            if amount <= 0:
                return False, "Amount must be positive"
            if self.current_user["balance"] < amount:
                return False, "Insufficient Balance"
            
            new_balance = self.current_user["balance"] - amount
            self.db.update_balance(self.current_user["account_number"], new_balance)
            self.current_user["balance"] = new_balance
            
            # Log transaction
            self.db.add_transaction(self.current_user["id"], "WITHDRAW", amount, description="Withdrawal")
            
            return True, f"Withdrew ₹{amount}. New Balance: ₹{new_balance}"
        except ValueError:
            return False, "Invalid amount"

    def transfer(self, recipient_account, amount):
        """Transfer money to another account"""
        if not self.current_user:
            return False, "Not logged in"
        
        try:
            amount = int(amount)
            if amount <= 0:
                return False, "Amount must be positive"
            
            if recipient_account == self.current_user["account_number"]:
                return False, "Cannot transfer to your own account"
            
            success, message = self.db.transfer_money(
                self.current_user["account_number"],
                recipient_account,
                amount
            )
            
            if success:
                # Update current user balance
                user = self.db.get_user_by_account(self.current_user["account_number"])
                self.current_user["balance"] = user[4]
            
            return success, message
        except ValueError:
            return False, "Invalid amount"

    def get_transaction_history(self, limit=50):
        """Get transaction history for current user"""
        if not self.current_user:
            return []
        return self.db.get_transaction_history(self.current_user["id"], limit)

    def get_account_info(self):
        """Get current user account information"""
        if not self.current_user:
            return None
        return {
            "name": self.current_user["name"],
            "account_number": self.current_user["account_number"],
            "balance": self.current_user["balance"],
            "created_at": self.current_user.get("created_at", "N/A")
        }

    def get_balance(self):
        if self.current_user:
            return self.current_user["balance"]
        return 0

    def logout(self):
        self.current_user = None

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class BankApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.controller = BankController()

        self.title("SecureBank - Professional Banking")
        self.geometry("1000x700")
        self.resizable(False, False)

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_frame = None
        self.show_login_frame()

    def switch_frame(self, frame_class, **kwargs):
        if self.current_frame:
            self.current_frame.destroy()
        
        self.current_frame = frame_class(self, **kwargs)
        self.current_frame.grid(row=0, column=0, sticky="nsew")

    def show_login_frame(self):
        self.switch_frame(LoginFrame)

    def show_register_frame(self):
        self.switch_frame(RegisterFrame)

    def show_dashboard_frame(self):
        self.switch_frame(DashboardFrame)

    def show_transaction_history_frame(self):
        self.switch_frame(TransactionHistoryFrame)

    def show_transfer_frame(self):
        self.switch_frame(TransferFrame)

    def show_account_details_frame(self):
        self.switch_frame(AccountDetailsFrame)

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#E3F2FD", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#1B263B"), corner_radius=20, width=450, height=550)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Title with gradient effect (simulated with color)
        title = ctk.CTkLabel(container, text="🏦 SecureBank", font=ctk.CTkFont(size=36, weight="bold"), 
                            text_color=("#1E88E5", "#42A5F5"))
        title.pack(pady=(50, 10))

        subtitle = ctk.CTkLabel(container, text="Welcome Back", font=ctk.CTkFont(size=18), 
                               text_color=("#546E7A", "#90A4AE"))
        subtitle.pack(pady=(0, 40))

        # Account Number Entry
        self.acc_entry = ctk.CTkEntry(container, placeholder_text="Account Number", width=350, height=45,
                                     font=ctk.CTkFont(size=14), corner_radius=10)
        self.acc_entry.pack(pady=15)

        # PIN Entry
        self.pin_entry = ctk.CTkEntry(container, placeholder_text="4-Digit PIN", show="●", width=350, height=45,
                                     font=ctk.CTkFont(size=14), corner_radius=10)
        self.pin_entry.pack(pady=15)
        self.pin_entry.bind("<Return>", lambda e: self.login_event())

        # Login Button with hover effect
        self.login_button = ctk.CTkButton(container, text="Sign In", command=self.login_event,
                                         width=350, height=45, font=ctk.CTkFont(size=16, weight="bold"),
                                         corner_radius=10, fg_color=("#1E88E5", "#1565C0"),
                                         hover_color=("#1565C0", "#0D47A1"))
        self.login_button.pack(pady=25)

        # Divider
        divider_frame = ctk.CTkFrame(container, fg_color="transparent", height=20)
        divider_frame.pack(pady=10)
        ctk.CTkLabel(divider_frame, text="Don't have an account?", 
                    text_color=("#78909C", "#B0BEC5"), font=ctk.CTkFont(size=12)).pack()

        # Register Link
        self.register_link = ctk.CTkButton(container, text="Create New Account", 
                                          fg_color="transparent", border_width=2, 
                                          border_color=("#1E88E5", "#42A5F5"),
                                          text_color=("#1E88E5", "#42A5F5"), 
                                          command=self.master.show_register_frame,
                                          width=350, height=40, corner_radius=10,
                                          hover_color=("#E3F2FD", "#1A2332"))
        self.register_link.pack(pady=10)

    def login_event(self):
        acc_num = self.acc_entry.get()
        pin = self.pin_entry.get()
        
        if not acc_num or not pin:
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        success, message = self.master.controller.sign_in(acc_num, pin)
        if success:
            self.master.show_dashboard_frame()
        else:
            messagebox.showerror("Login Error", message)

class RegisterFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#E8F5E9", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#1B263B"), corner_radius=20, width=450, height=550)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="🌟 Create Account", font=ctk.CTkFont(size=36, weight="bold"), 
                            text_color=("#43A047", "#66BB6A"))
        title.pack(pady=(50, 10))

        subtitle = ctk.CTkLabel(container, text="Join SecureBank Today", font=ctk.CTkFont(size=18), 
                               text_color=("#546E7A", "#90A4AE"))
        subtitle.pack(pady=(0, 40))

        # Name Entry
        self.name_entry = ctk.CTkEntry(container, placeholder_text="Full Name", width=350, height=45,
                                      font=ctk.CTkFont(size=14), corner_radius=10)
        self.name_entry.pack(pady=15)

        # PIN Entry
        self.pin_entry = ctk.CTkEntry(container, placeholder_text="Create 4-Digit PIN", show="●", width=350, height=45,
                                     font=ctk.CTkFont(size=14), corner_radius=10)
        self.pin_entry.pack(pady=15)
        self.pin_entry.bind("<Return>", lambda e: self.register_event())

        # Register Button
        self.register_button = ctk.CTkButton(container, text="Create Account", command=self.register_event,
                                            width=350, height=45, font=ctk.CTkFont(size=16, weight="bold"),
                                            corner_radius=10, fg_color=("#43A047", "#2E7D32"),
                                            hover_color=("#2E7D32", "#1B5E20"))
        self.register_button.pack(pady=25)

        # Divider
        divider_frame = ctk.CTkFrame(container, fg_color="transparent", height=20)
        divider_frame.pack(pady=10)
        ctk.CTkLabel(divider_frame, text="Already have an account?", 
                    text_color=("#78909C", "#B0BEC5"), font=ctk.CTkFont(size=12)).pack()

        # Back to Login
        self.login_link = ctk.CTkButton(container, text="Back to Login", 
                                       fg_color="transparent", border_width=2, 
                                       border_color=("#43A047", "#66BB6A"),
                                       text_color=("#43A047", "#66BB6A"), 
                                       command=self.master.show_login_frame,
                                       width=350, height=40, corner_radius=10,
                                       hover_color=("#E8F5E9", "#1A2332"))
        self.login_link.pack(pady=10)

    def register_event(self):
        name = self.name_entry.get()
        pin = self.pin_entry.get()
        
        if not name or not pin:
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        message = self.master.controller.sign_up(name, pin)
        if "Account Created" in message:
            messagebox.showinfo("Success", message + "\n\nPlease save your account number!")
            self.master.show_login_frame()
        else:
            messagebox.showerror("Error", message)

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#F5F5F5", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=("#1E88E5", "#1565C0"), height=100, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        user_name = self.master.controller.current_user['name']
        welcome = ctk.CTkLabel(header, text=f"Welcome, {user_name}!", 
                              font=ctk.CTkFont(size=28, weight="bold"), text_color="white")
        welcome.pack(pady=(20, 5))

        account_num = self.master.controller.current_user['account_number']
        acc_label = ctk.CTkLabel(header, text=f"Account: {account_num}", 
                                font=ctk.CTkFont(size=14), text_color=("#E3F2FD", "#B3E5FC"))
        acc_label.pack(pady=(0, 20))

        # Main content area
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure((0, 1, 2), weight=1)

        # Balance Card
        balance_card = ctk.CTkFrame(content, fg_color=("#FFFFFF", "#1B263B"), corner_radius=15, height=150)
        balance_card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 20))
        
        ctk.CTkLabel(balance_card, text="💰 Current Balance", 
                    font=ctk.CTkFont(size=16), text_color=("#546E7A", "#90A4AE")).pack(pady=(20, 5))
        
        self.balance_label = ctk.CTkLabel(balance_card, text=f"₹{self.master.controller.get_balance():,}", 
                                         font=ctk.CTkFont(size=42, weight="bold"), 
                                         text_color=("#1E88E5", "#42A5F5"))
        self.balance_label.pack(pady=(0, 20))

        # Quick Actions Title
        ctk.CTkLabel(content, text="Quick Actions", font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=("#263238", "#ECEFF1")).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 15))

        # Action Cards
        # Deposit Card
        deposit_card = ctk.CTkFrame(content, fg_color=("#E8F5E9", "#1B5E20"), corner_radius=15)
        deposit_card.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(deposit_card, text="💵", font=ctk.CTkFont(size=40)).pack(pady=(20, 10))
        ctk.CTkLabel(deposit_card, text="Deposit Money", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=("#1B5E20", "#A5D6A7")).pack()
        self.deposit_entry = ctk.CTkEntry(deposit_card, placeholder_text="Amount", width=150, height=35)
        self.deposit_entry.pack(pady=10)
        ctk.CTkButton(deposit_card, text="Deposit", command=self.deposit_event, width=150,
                     fg_color=("#43A047", "#2E7D32"), hover_color=("#2E7D32", "#1B5E20")).pack(pady=(5, 20))

        # Withdraw Card
        withdraw_card = ctk.CTkFrame(content, fg_color=("#FFEBEE", "#B71C1C"), corner_radius=15)
        withdraw_card.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(withdraw_card, text="💸", font=ctk.CTkFont(size=40)).pack(pady=(20, 10))
        ctk.CTkLabel(withdraw_card, text="Withdraw Money", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=("#B71C1C", "#EF9A9A")).pack()
        self.withdraw_entry = ctk.CTkEntry(withdraw_card, placeholder_text="Amount", width=150, height=35)
        self.withdraw_entry.pack(pady=10)
        ctk.CTkButton(withdraw_card, text="Withdraw", command=self.withdraw_event, width=150,
                     fg_color=("#E53935", "#C62828"), hover_color=("#C62828", "#B71C1C")).pack(pady=(5, 20))

        # Transfer Card
        transfer_card = ctk.CTkFrame(content, fg_color=("#FFF3E0", "#E65100"), corner_radius=15)
        transfer_card.grid(row=2, column=2, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(transfer_card, text="🔄", font=ctk.CTkFont(size=40)).pack(pady=(20, 10))
        ctk.CTkLabel(transfer_card, text="Transfer Money", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=("#E65100", "#FFCC80")).pack()
        ctk.CTkButton(transfer_card, text="Go to Transfer", command=self.master.show_transfer_frame, width=150,
                     fg_color=("#FB8C00", "#EF6C00"), hover_color=("#EF6C00", "#E65100")).pack(pady=(30, 20))

        # Navigation Buttons
        nav_frame = ctk.CTkFrame(content, fg_color="transparent")
        nav_frame.grid(row=3, column=0, columnspan=3, pady=30)

        ctk.CTkButton(nav_frame, text="📊 Transaction History", command=self.master.show_transaction_history_frame,
                     width=200, height=40, fg_color=("#5E35B1", "#4527A0"), 
                     hover_color=("#4527A0", "#311B92")).pack(side="left", padx=10)

        ctk.CTkButton(nav_frame, text="👤 Account Details", command=self.master.show_account_details_frame,
                     width=200, height=40, fg_color=("#00897B", "#00695C"), 
                     hover_color=("#00695C", "#004D40")).pack(side="left", padx=10)

        ctk.CTkButton(nav_frame, text="🚪 Logout", command=self.logout_event,
                     width=150, height=40, fg_color=("#757575", "#424242"), 
                     hover_color=("#616161", "#212121")).pack(side="left", padx=10)

    def refresh_balance(self):
        self.balance_label.configure(text=f"₹{self.master.controller.get_balance():,}")

    def deposit_event(self):
        amount = self.deposit_entry.get()
        if not amount:
            messagebox.showerror("Error", "Please enter amount")
            return
        success, msg = self.master.controller.deposit(amount)
        if success:
            self.refresh_balance()
            messagebox.showinfo("Success", msg)
            self.deposit_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

    def withdraw_event(self):
        amount = self.withdraw_entry.get()
        if not amount:
            messagebox.showerror("Error", "Please enter amount")
            return
        success, msg = self.master.controller.withdraw(amount)
        if success:
            self.refresh_balance()
            messagebox.showinfo("Success", msg)
            self.withdraw_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

    def logout_event(self):
        self.master.controller.logout()
        self.master.show_login_frame()

class TransactionHistoryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#F5F5F5", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=("#5E35B1", "#4527A0"), height=80, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="📊 Transaction History", 
                            font=ctk.CTkFont(size=28, weight="bold"), text_color="white")
        title.pack(pady=20)

        # Content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        content.grid_columnconfigure(0, weight=1)

        # Get transactions
        transactions = self.master.controller.get_transaction_history()

        if not transactions:
            no_trans = ctk.CTkLabel(content, text="No transactions yet", 
                                   font=ctk.CTkFont(size=18), text_color=("#9E9E9E", "#757575"))
            no_trans.pack(pady=50)
        else:
            for idx, trans in enumerate(transactions):
                trans_type, amount, recipient, timestamp, description = trans
                
                # Transaction card
                card_color = ("#E8F5E9", "#1B5E20") if trans_type == "DEPOSIT" or trans_type == "TRANSFER_IN" else ("#FFEBEE", "#B71C1C")
                if trans_type.startswith("TRANSFER"):
                    card_color = ("#FFF3E0", "#E65100")
                
                card = ctk.CTkFrame(content, fg_color=("#FFFFFF", "#1B263B"), corner_radius=10)
                card.grid(row=idx, column=0, sticky="ew", pady=5)
                card.grid_columnconfigure(1, weight=1)

                # Icon
                icon_map = {"DEPOSIT": "💵", "WITHDRAW": "💸", "TRANSFER_OUT": "📤", "TRANSFER_IN": "📥"}
                icon = ctk.CTkLabel(card, text=icon_map.get(trans_type, "💰"), font=ctk.CTkFont(size=24))
                icon.grid(row=0, column=0, padx=20, pady=15)

                # Details
                details_frame = ctk.CTkFrame(card, fg_color="transparent")
                details_frame.grid(row=0, column=1, sticky="ew", pady=15)

                type_label = ctk.CTkLabel(details_frame, text=trans_type.replace("_", " ").title(), 
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=("#263238", "#ECEFF1"))
                type_label.pack(anchor="w")

                if description:
                    desc_label = ctk.CTkLabel(details_frame, text=description, 
                                             font=ctk.CTkFont(size=12),
                                             text_color=("#546E7A", "#90A4AE"))
                    desc_label.pack(anchor="w")

                time_label = ctk.CTkLabel(details_frame, text=timestamp, 
                                         font=ctk.CTkFont(size=11),
                                         text_color=("#78909C", "#78909C"))
                time_label.pack(anchor="w")

                # Amount
                amount_color = ("#43A047", "#66BB6A") if trans_type in ["DEPOSIT", "TRANSFER_IN"] else ("#E53935", "#EF5350")
                amount_prefix = "+" if trans_type in ["DEPOSIT", "TRANSFER_IN"] else "-"
                amount_label = ctk.CTkLabel(card, text=f"{amount_prefix}₹{amount:,}", 
                                           font=ctk.CTkFont(size=18, weight="bold"),
                                           text_color=amount_color)
                amount_label.grid(row=0, column=2, padx=20)

        # Back button
        back_btn = ctk.CTkButton(self, text="← Back to Dashboard", command=self.master.show_dashboard_frame,
                                width=200, height=40, fg_color=("#757575", "#424242"),
                                hover_color=("#616161", "#212121"))
        back_btn.grid(row=2, column=0, pady=20)

class TransferFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#FFF3E0", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#1B263B"), corner_radius=20, width=500, height=500)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="🔄 Transfer Money", font=ctk.CTkFont(size=32, weight="bold"), 
                            text_color=("#FB8C00", "#FFB74D"))
        title.pack(pady=(40, 10))

        subtitle = ctk.CTkLabel(container, text="Send money to another account", font=ctk.CTkFont(size=14), 
                               text_color=("#546E7A", "#90A4AE"))
        subtitle.pack(pady=(0, 30))

        # Recipient Account
        ctk.CTkLabel(container, text="Recipient Account Number", font=ctk.CTkFont(size=12),
                    text_color=("#546E7A", "#90A4AE")).pack(anchor="w", padx=75)
        self.recipient_entry = ctk.CTkEntry(container, placeholder_text="Enter account number", width=350, height=45,
                                           font=ctk.CTkFont(size=14), corner_radius=10)
        self.recipient_entry.pack(pady=(5, 20))

        # Amount
        ctk.CTkLabel(container, text="Amount", font=ctk.CTkFont(size=12),
                    text_color=("#546E7A", "#90A4AE")).pack(anchor="w", padx=75)
        self.amount_entry = ctk.CTkEntry(container, placeholder_text="Enter amount", width=350, height=45,
                                        font=ctk.CTkFont(size=14), corner_radius=10)
        self.amount_entry.pack(pady=(5, 30))
        self.amount_entry.bind("<Return>", lambda e: self.transfer_event())

        # Transfer Button
        self.transfer_button = ctk.CTkButton(container, text="Transfer Now", command=self.transfer_event,
                                            width=350, height=50, font=ctk.CTkFont(size=16, weight="bold"),
                                            corner_radius=10, fg_color=("#FB8C00", "#F57C00"),
                                            hover_color=("#F57C00", "#EF6C00"))
        self.transfer_button.pack(pady=10)

        # Back Button
        back_btn = ctk.CTkButton(container, text="← Back to Dashboard", command=self.master.show_dashboard_frame,
                                width=350, height=40, fg_color="transparent", border_width=2,
                                border_color=("#FB8C00", "#FFB74D"), text_color=("#FB8C00", "#FFB74D"),
                                corner_radius=10, hover_color=("#FFF3E0", "#1A2332"))
        back_btn.pack(pady=10)

    def transfer_event(self):
        recipient = self.recipient_entry.get()
        amount = self.amount_entry.get()

        if not recipient or not amount:
            messagebox.showerror("Error", "Please fill all fields")
            return

        success, msg = self.master.controller.transfer(recipient, amount)
        if success:
            messagebox.showinfo("Success", msg)
            self.recipient_entry.delete(0, 'end')
            self.amount_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

class AccountDetailsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#E0F2F1", "#0D1B2A"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#1B263B"), corner_radius=20, width=500, height=550)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="👤 Account Details", font=ctk.CTkFont(size=32, weight="bold"), 
                            text_color=("#00897B", "#4DB6AC"))
        title.pack(pady=(40, 40))

        # Get account info
        info = self.master.controller.get_account_info()

        if info:
            # Info cards
            details = [
                ("👤 Account Holder", info['name']),
                ("🔢 Account Number", info['account_number']),
                ("💰 Current Balance", f"₹{info['balance']:,}"),
                ("📅 Account Created", str(info['created_at'])[:19] if info['created_at'] else "N/A")
            ]

            for icon_label, value in details:
                card = ctk.CTkFrame(container, fg_color=("#E0F2F1", "#1B5E20"), corner_radius=10, height=70)
                card.pack(fill="x", padx=40, pady=10)

                ctk.CTkLabel(card, text=icon_label, font=ctk.CTkFont(size=12),
                            text_color=("#00695C", "#80CBC4")).pack(anchor="w", padx=20, pady=(10, 0))
                ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"),
                            text_color=("#004D40", "#B2DFDB")).pack(anchor="w", padx=20, pady=(0, 10))

        # Back Button
        back_btn = ctk.CTkButton(container, text="← Back to Dashboard", command=self.master.show_dashboard_frame,
                                width=350, height=45, fg_color=("#00897B", "#00695C"),
                                hover_color=("#00695C", "#004D40"), corner_radius=10)
        back_btn.pack(pady=30)

if __name__ == "__main__":
    app = BankApp()
    app.mainloop()
