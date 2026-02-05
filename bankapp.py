import sqlite3
import random
import os
from tkinter import messagebox
from datetime import datetime
import customtkinter as ctk

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

# Set appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Professional Color Palette
COLORS = {
    "primary": "#667eea",
    "primary_dark": "#5568d3",
    "secondary": "#764ba2",
    "success": "#10b981",
    "success_dark": "#059669",
    "error": "#ef4444",
    "error_dark": "#dc2626",
    "warning": "#f59e0b",
    "warning_dark": "#d97706",
    "info": "#3b82f6",
    "background_light": "#f8fafc",
    "background_dark": "#0f172a",
    "card_light": "#ffffff",
    "card_dark": "#1e293b",
    "text_primary": "#1e293b",
    "text_secondary": "#64748b",
    "text_light": "#f1f5f9",
    "border": "#e2e8f0",
}

class AnimatedButton(ctk.CTkButton):
    """Custom button with hover animation"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        
    def on_enter(self, event):
        self.configure(cursor="hand2")
        
    def on_leave(self, event):
        self.configure(cursor="")

class BankApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.controller = BankController()

        self.title("SecureBank Pro - Modern Banking Experience")
        self.geometry("1200x800")
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
        super().__init__(master, fg_color=("#e0e7ff", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Animated background gradient effect (simulated with layered frames)
        bg_layer = ctk.CTkFrame(self, fg_color=("#ddd6fe", "#1e1b4b"), corner_radius=0)
        bg_layer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main container with glassmorphism effect
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, 
                                 width=500, height=600, border_width=2, 
                                 border_color=("#e0e7ff", "#334155"))
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Logo/Icon area with gradient background
        logo_frame = ctk.CTkFrame(container, fg_color=("#667eea", "#5b21b6"), 
                                  corner_radius=20, height=100, width=100)
        logo_frame.pack(pady=(40, 20))
        
        logo_label = ctk.CTkLabel(logo_frame, text="🏦", font=ctk.CTkFont(size=50))
        logo_label.place(relx=0.5, rely=0.5, anchor="center")

        # Title with modern typography
        title = ctk.CTkLabel(container, text="SecureBank Pro", 
                            font=ctk.CTkFont(size=38, weight="bold"), 
                            text_color=("#667eea", "#a78bfa"))
        title.pack(pady=(10, 5))

        subtitle = ctk.CTkLabel(container, text="Welcome back! Please login to continue", 
                               font=ctk.CTkFont(size=14), 
                               text_color=("#64748b", "#94a3b8"))
        subtitle.pack(pady=(0, 40))

        # Account Number Entry with enhanced styling
        acc_label = ctk.CTkLabel(container, text="Account Number", 
                                font=ctk.CTkFont(size=12, weight="bold"),
                                text_color=("#475569", "#cbd5e1"))
        acc_label.pack(anchor="w", padx=75, pady=(0, 5))
        
        self.acc_entry = ctk.CTkEntry(container, placeholder_text="Enter your account number", 
                                      width=350, height=50,
                                      font=ctk.CTkFont(size=15), corner_radius=12,
                                      border_width=2, border_color=("#e2e8f0", "#334155"))
        self.acc_entry.pack(pady=(0, 20))

        # PIN Entry with enhanced styling
        pin_label = ctk.CTkLabel(container, text="PIN", 
                                font=ctk.CTkFont(size=12, weight="bold"),
                                text_color=("#475569", "#cbd5e1"))
        pin_label.pack(anchor="w", padx=75, pady=(0, 5))
        
        self.pin_entry = ctk.CTkEntry(container, placeholder_text="Enter 4-digit PIN", 
                                      show="●", width=350, height=50,
                                      font=ctk.CTkFont(size=15), corner_radius=12,
                                      border_width=2, border_color=("#e2e8f0", "#334155"))
        self.pin_entry.pack(pady=(0, 30))
        self.pin_entry.bind("<Return>", lambda e: self.login_event())

        # Login Button with gradient effect
        self.login_button = AnimatedButton(container, text="Sign In →", 
                                          command=self.login_event,
                                          width=350, height=50, 
                                          font=ctk.CTkFont(size=17, weight="bold"),
                                          corner_radius=12, fg_color=("#667eea", "#7c3aed"),
                                          hover_color=("#5568d3", "#6d28d9"))
        self.login_button.pack(pady=(0, 20))

        # Divider with text
        divider_frame = ctk.CTkFrame(container, fg_color="transparent", height=30)
        divider_frame.pack(pady=15, fill="x", padx=75)
        
        ctk.CTkFrame(divider_frame, fg_color=("#cbd5e1", "#475569"), 
                    height=1).pack(side="left", fill="x", expand=True, pady=15)
        ctk.CTkLabel(divider_frame, text=" OR ", 
                    text_color=("#94a3b8", "#64748b"), 
                    font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
        ctk.CTkFrame(divider_frame, fg_color=("#cbd5e1", "#475569"), 
                    height=1).pack(side="left", fill="x", expand=True, pady=15)

        # Register Link with modern styling
        self.register_link = AnimatedButton(container, text="Create New Account", 
                                           fg_color="transparent", border_width=2, 
                                           border_color=("#667eea", "#a78bfa"),
                                           text_color=("#667eea", "#a78bfa"), 
                                           command=self.master.show_register_frame,
                                           width=350, height=48, corner_radius=12,
                                           hover_color=("#f1f5f9", "#1e293b"),
                                           font=ctk.CTkFont(size=15, weight="bold"))
        self.register_link.pack(pady=(0, 30))

    def login_event(self):
        acc_num = self.acc_entry.get().strip()
        pin = self.pin_entry.get().strip()
        
        if not acc_num or not pin:
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        # Disable button during processing
        self.login_button.configure(state="disabled", text="Signing in...")
        self.update()
        
        success, message = self.master.controller.sign_in(acc_num, pin)
        
        if success:
            self.master.show_dashboard_frame()
        else:
            self.login_button.configure(state="normal", text="Sign In →")
            messagebox.showerror("Login Error", message)

class RegisterFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#dcfce7", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Animated background
        bg_layer = ctk.CTkFrame(self, fg_color=("#bbf7d0", "#14532d"), corner_radius=0)
        bg_layer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, 
                                 width=500, height=600, border_width=2,
                                 border_color=("#dcfce7", "#334155"))
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Logo area
        logo_frame = ctk.CTkFrame(container, fg_color=("#10b981", "#059669"), 
                                  corner_radius=20, height=100, width=100)
        logo_frame.pack(pady=(40, 20))
        
        logo_label = ctk.CTkLabel(logo_frame, text="✨", font=ctk.CTkFont(size=50))
        logo_label.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="Join SecureBank", 
                            font=ctk.CTkFont(size=38, weight="bold"), 
                            text_color=("#10b981", "#34d399"))
        title.pack(pady=(10, 5))

        subtitle = ctk.CTkLabel(container, text="Create your account in seconds", 
                               font=ctk.CTkFont(size=14), 
                               text_color=("#64748b", "#94a3b8"))
        subtitle.pack(pady=(0, 40))

        # Name Entry
        name_label = ctk.CTkLabel(container, text="Full Name", 
                                 font=ctk.CTkFont(size=12, weight="bold"),
                                 text_color=("#475569", "#cbd5e1"))
        name_label.pack(anchor="w", padx=75, pady=(0, 5))
        
        self.name_entry = ctk.CTkEntry(container, placeholder_text="Enter your full name", 
                                       width=350, height=50,
                                       font=ctk.CTkFont(size=15), corner_radius=12,
                                       border_width=2, border_color=("#e2e8f0", "#334155"))
        self.name_entry.pack(pady=(0, 20))

        # PIN Entry
        pin_label = ctk.CTkLabel(container, text="Create PIN", 
                                font=ctk.CTkFont(size=12, weight="bold"),
                                text_color=("#475569", "#cbd5e1"))
        pin_label.pack(anchor="w", padx=75, pady=(0, 5))
        
        self.pin_entry = ctk.CTkEntry(container, placeholder_text="Create 4-digit PIN", 
                                      show="●", width=350, height=50,
                                      font=ctk.CTkFont(size=15), corner_radius=12,
                                      border_width=2, border_color=("#e2e8f0", "#334155"))
        self.pin_entry.pack(pady=(0, 30))
        self.pin_entry.bind("<Return>", lambda e: self.register_event())

        # Register Button
        self.register_button = AnimatedButton(container, text="Create Account →", 
                                             command=self.register_event,
                                             width=350, height=50, 
                                             font=ctk.CTkFont(size=17, weight="bold"),
                                             corner_radius=12, fg_color=("#10b981", "#059669"),
                                             hover_color=("#059669", "#047857"))
        self.register_button.pack(pady=(0, 20))

        # Divider
        divider_frame = ctk.CTkFrame(container, fg_color="transparent", height=30)
        divider_frame.pack(pady=15, fill="x", padx=75)
        
        ctk.CTkFrame(divider_frame, fg_color=("#cbd5e1", "#475569"), 
                    height=1).pack(side="left", fill="x", expand=True, pady=15)
        ctk.CTkLabel(divider_frame, text=" OR ", 
                    text_color=("#94a3b8", "#64748b"), 
                    font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
        ctk.CTkFrame(divider_frame, fg_color=("#cbd5e1", "#475569"), 
                    height=1).pack(side="left", fill="x", expand=True, pady=15)

        # Back to Login
        self.login_link = AnimatedButton(container, text="Already have an account? Sign In", 
                                        fg_color="transparent", border_width=2, 
                                        border_color=("#10b981", "#34d399"),
                                        text_color=("#10b981", "#34d399"), 
                                        command=self.master.show_login_frame,
                                        width=350, height=48, corner_radius=12,
                                        hover_color=("#f0fdf4", "#1e293b"),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self.login_link.pack(pady=(0, 30))

    def register_event(self):
        name = self.name_entry.get().strip()
        pin = self.pin_entry.get().strip()
        
        if not name or not pin:
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        if len(pin) != 4 or not pin.isdigit():
            messagebox.showerror("Error", "PIN must be exactly 4 digits")
            return
        
        # Disable button during processing
        self.register_button.configure(state="disabled", text="Creating account...")
        self.update()
        
        message = self.master.controller.sign_up(name, pin)
        
        if "Account Created" in message:
            messagebox.showinfo("Success! 🎉", message + "\n\n⚠️ Please save your account number securely!")
            self.master.show_login_frame()
        else:
            self.register_button.configure(state="normal", text="Create Account →")
            messagebox.showerror("Error", message)

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#f8fafc", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Modern gradient header
        header = ctk.CTkFrame(self, fg_color=("#667eea", "#5b21b6"), height=120, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        user_name = self.master.controller.current_user['name']
        welcome = ctk.CTkLabel(header, text=f"Welcome back, {user_name}! 👋", 
                              font=ctk.CTkFont(size=32, weight="bold"), text_color="white")
        welcome.pack(pady=(25, 5))

        account_num = self.master.controller.current_user['account_number']
        acc_label = ctk.CTkLabel(header, text=f"Account: {account_num}", 
                                font=ctk.CTkFont(size=15), text_color=("#e0e7ff", "#ddd6fe"))
        acc_label.pack(pady=(0, 25))

        # Main content area
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=30, pady=30)
        content.grid_columnconfigure((0, 1, 2), weight=1)

        # Enhanced Balance Card with gradient
        balance_card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                    corner_radius=20, height=180, border_width=0)
        balance_card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 30))
        
        # Balance card gradient accent
        accent_bar = ctk.CTkFrame(balance_card, fg_color=("#667eea", "#7c3aed"), 
                                  height=8, corner_radius=20)
        accent_bar.pack(fill="x", pady=(0, 0))
        
        ctk.CTkLabel(balance_card, text="💰 Total Balance", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=("#64748b", "#94a3b8")).pack(pady=(30, 10))
        
        self.balance_label = ctk.CTkLabel(balance_card, 
                                         text=f"₹{self.master.controller.get_balance():,}", 
                                         font=ctk.CTkFont(size=52, weight="bold"), 
                                         text_color=("#667eea", "#a78bfa"))
        self.balance_label.pack(pady=(0, 30))

        # Quick Actions Title
        actions_title = ctk.CTkLabel(content, text="⚡ Quick Actions", 
                                    font=ctk.CTkFont(size=24, weight="bold"),
                                    text_color=("#1e293b", "#f1f5f9"))
        actions_title.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 20))

        # Enhanced Action Cards with modern design
        # Deposit Card
        deposit_card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                    corner_radius=20, border_width=0)
        deposit_card.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        deposit_accent = ctk.CTkFrame(deposit_card, fg_color=("#10b981", "#059669"), 
                                      height=6, corner_radius=20)
        deposit_accent.pack(fill="x")
        
        ctk.CTkLabel(deposit_card, text="💵", font=ctk.CTkFont(size=48)).pack(pady=(30, 15))
        ctk.CTkLabel(deposit_card, text="Deposit Money", 
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=("#10b981", "#34d399")).pack(pady=(0, 5))
        ctk.CTkLabel(deposit_card, text="Add funds to account", 
                    font=ctk.CTkFont(size=12),
                    text_color=("#64748b", "#94a3b8")).pack(pady=(0, 20))
        
        self.deposit_entry = ctk.CTkEntry(deposit_card, placeholder_text="Amount", 
                                         width=180, height=42, corner_radius=10,
                                         font=ctk.CTkFont(size=14))
        self.deposit_entry.pack(pady=(0, 15))
        
        AnimatedButton(deposit_card, text="Deposit", command=self.deposit_event, 
                      width=180, height=42, corner_radius=10,
                      fg_color=("#10b981", "#059669"), 
                      hover_color=("#059669", "#047857"),
                      font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(0, 30))

        # Withdraw Card
        withdraw_card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                     corner_radius=20, border_width=0)
        withdraw_card.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        
        withdraw_accent = ctk.CTkFrame(withdraw_card, fg_color=("#ef4444", "#dc2626"), 
                                       height=6, corner_radius=20)
        withdraw_accent.pack(fill="x")
        
        ctk.CTkLabel(withdraw_card, text="💸", font=ctk.CTkFont(size=48)).pack(pady=(30, 15))
        ctk.CTkLabel(withdraw_card, text="Withdraw Money", 
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=("#ef4444", "#f87171")).pack(pady=(0, 5))
        ctk.CTkLabel(withdraw_card, text="Take out cash", 
                    font=ctk.CTkFont(size=12),
                    text_color=("#64748b", "#94a3b8")).pack(pady=(0, 20))
        
        self.withdraw_entry = ctk.CTkEntry(withdraw_card, placeholder_text="Amount", 
                                          width=180, height=42, corner_radius=10,
                                          font=ctk.CTkFont(size=14))
        self.withdraw_entry.pack(pady=(0, 15))
        
        AnimatedButton(withdraw_card, text="Withdraw", command=self.withdraw_event, 
                      width=180, height=42, corner_radius=10,
                      fg_color=("#ef4444", "#dc2626"), 
                      hover_color=("#dc2626", "#b91c1c"),
                      font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(0, 30))

        # Transfer Card
        transfer_card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                     corner_radius=20, border_width=0)
        transfer_card.grid(row=2, column=2, sticky="nsew", padx=10, pady=10)
        
        transfer_accent = ctk.CTkFrame(transfer_card, fg_color=("#f59e0b", "#d97706"), 
                                       height=6, corner_radius=20)
        transfer_accent.pack(fill="x")
        
        ctk.CTkLabel(transfer_card, text="🔄", font=ctk.CTkFont(size=48)).pack(pady=(30, 15))
        ctk.CTkLabel(transfer_card, text="Transfer Money", 
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=("#f59e0b", "#fbbf24")).pack(pady=(0, 5))
        ctk.CTkLabel(transfer_card, text="Send to others", 
                    font=ctk.CTkFont(size=12),
                    text_color=("#64748b", "#94a3b8")).pack(pady=(0, 20))
        
        AnimatedButton(transfer_card, text="Go to Transfer →", 
                      command=self.master.show_transfer_frame, 
                      width=180, height=42, corner_radius=10,
                      fg_color=("#f59e0b", "#d97706"), 
                      hover_color=("#d97706", "#b45309"),
                      font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(50, 30))

        # Navigation Section
        nav_title = ctk.CTkLabel(content, text="📊 Account Management", 
                                font=ctk.CTkFont(size=24, weight="bold"),
                                text_color=("#1e293b", "#f1f5f9"))
        nav_title.grid(row=3, column=0, columnspan=3, sticky="w", pady=(30, 20))

        # Navigation Cards
        nav_frame = ctk.CTkFrame(content, fg_color="transparent")
        nav_frame.grid(row=4, column=0, columnspan=3, pady=(0, 20))

        AnimatedButton(nav_frame, text="📊 Transaction History", 
                      command=self.master.show_transaction_history_frame,
                      width=240, height=50, fg_color=("#8b5cf6", "#7c3aed"), 
                      hover_color=("#7c3aed", "#6d28d9"),
                      corner_radius=12,
                      font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=10)

        AnimatedButton(nav_frame, text="👤 Account Details", 
                      command=self.master.show_account_details_frame,
                      width=240, height=50, fg_color=("#06b6d4", "#0891b2"), 
                      hover_color=("#0891b2", "#0e7490"),
                      corner_radius=12,
                      font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=10)

        AnimatedButton(nav_frame, text="🚪 Logout", command=self.logout_event,
                      width=180, height=50, fg_color=("#64748b", "#475569"), 
                      hover_color=("#475569", "#334155"),
                      corner_radius=12,
                      font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=10)

    def refresh_balance(self):
        self.balance_label.configure(text=f"₹{self.master.controller.get_balance():,}")

    def deposit_event(self):
        amount = self.deposit_entry.get().strip()
        if not amount:
            messagebox.showerror("Error", "Please enter amount")
            return
        success, msg = self.master.controller.deposit(amount)
        if success:
            self.refresh_balance()
            messagebox.showinfo("Success! ✅", msg)
            self.deposit_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

    def withdraw_event(self):
        amount = self.withdraw_entry.get().strip()
        if not amount:
            messagebox.showerror("Error", "Please enter amount")
            return
        success, msg = self.master.controller.withdraw(amount)
        if success:
            self.refresh_balance()
            messagebox.showinfo("Success! ✅", msg)
            self.withdraw_entry.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

    def logout_event(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.master.controller.logout()
            self.master.show_login_frame()

class TransactionHistoryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#f8fafc", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Modern header with gradient
        header = ctk.CTkFrame(self, fg_color=("#8b5cf6", "#6d28d9"), height=100, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="📊 Transaction History", 
                            font=ctk.CTkFont(size=32, weight="bold"), text_color="white")
        title.pack(pady=30)

        # Content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=30, pady=30)
        content.grid_columnconfigure(0, weight=1)

        # Get transactions
        transactions = self.master.controller.get_transaction_history()

        if not transactions:
            no_trans_card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                         corner_radius=20, height=200)
            no_trans_card.pack(fill="x", pady=20)
            
            ctk.CTkLabel(no_trans_card, text="📭", 
                        font=ctk.CTkFont(size=60)).pack(pady=(40, 20))
            ctk.CTkLabel(no_trans_card, text="No transactions yet", 
                        font=ctk.CTkFont(size=20, weight="bold"),
                        text_color=("#94a3b8", "#64748b")).pack(pady=(0, 10))
            ctk.CTkLabel(no_trans_card, text="Your transaction history will appear here", 
                        font=ctk.CTkFont(size=14),
                        text_color=("#cbd5e1", "#475569")).pack(pady=(0, 40))
        else:
            for idx, trans in enumerate(transactions):
                trans_type, amount, recipient, timestamp, description = trans
                
                # Transaction card with modern design
                card = ctk.CTkFrame(content, fg_color=("#ffffff", "#1e293b"), 
                                   corner_radius=15, border_width=0)
                card.grid(row=idx, column=0, sticky="ew", pady=8)
                card.grid_columnconfigure(1, weight=1)

                # Color-coded accent bar
                accent_colors = {
                    "DEPOSIT": ("#10b981", "#059669"),
                    "WITHDRAW": ("#ef4444", "#dc2626"),
                    "TRANSFER_OUT": ("#f59e0b", "#d97706"),
                    "TRANSFER_IN": ("#06b6d4", "#0891b2")
                }
                accent_color = accent_colors.get(trans_type, ("#64748b", "#475569"))
                
                accent = ctk.CTkFrame(card, fg_color=accent_color, width=6, corner_radius=15)
                accent.grid(row=0, column=0, sticky="ns", padx=(0, 15), pady=5)

                # Icon with background
                icon_map = {"DEPOSIT": "💵", "WITHDRAW": "💸", "TRANSFER_OUT": "📤", "TRANSFER_IN": "📥"}
                icon_bg = ctk.CTkFrame(card, fg_color=accent_color, corner_radius=12, 
                                       width=60, height=60)
                icon_bg.grid(row=0, column=1, padx=20, pady=20)
                
                icon = ctk.CTkLabel(icon_bg, text=icon_map.get(trans_type, "💰"), 
                                   font=ctk.CTkFont(size=28))
                icon.place(relx=0.5, rely=0.5, anchor="center")

                # Details
                details_frame = ctk.CTkFrame(card, fg_color="transparent")
                details_frame.grid(row=0, column=2, sticky="ew", pady=20)

                type_label = ctk.CTkLabel(details_frame, 
                                         text=trans_type.replace("_", " ").title(), 
                                         font=ctk.CTkFont(size=16, weight="bold"),
                                         text_color=("#1e293b", "#f1f5f9"))
                type_label.pack(anchor="w")

                if description:
                    desc_label = ctk.CTkLabel(details_frame, text=description, 
                                             font=ctk.CTkFont(size=13),
                                             text_color=("#64748b", "#94a3b8"))
                    desc_label.pack(anchor="w", pady=(2, 0))

                time_label = ctk.CTkLabel(details_frame, text=timestamp, 
                                         font=ctk.CTkFont(size=11),
                                         text_color=("#94a3b8", "#64748b"))
                time_label.pack(anchor="w", pady=(5, 0))

                # Amount with color coding
                amount_color = ("#10b981", "#34d399") if trans_type in ["DEPOSIT", "TRANSFER_IN"] else ("#ef4444", "#f87171")
                amount_prefix = "+" if trans_type in ["DEPOSIT", "TRANSFER_IN"] else "-"
                
                amount_frame = ctk.CTkFrame(card, fg_color="transparent")
                amount_frame.grid(row=0, column=3, padx=30)
                
                amount_label = ctk.CTkLabel(amount_frame, 
                                           text=f"{amount_prefix}₹{amount:,}", 
                                           font=ctk.CTkFont(size=20, weight="bold"),
                                           text_color=amount_color)
                amount_label.pack(anchor="e")

        # Back button
        back_btn = AnimatedButton(self, text="← Back to Dashboard", 
                                 command=self.master.show_dashboard_frame,
                                 width=220, height=50, fg_color=("#64748b", "#475569"),
                                 hover_color=("#475569", "#334155"),
                                 corner_radius=12,
                                 font=ctk.CTkFont(size=15, weight="bold"))
        back_btn.grid(row=2, column=0, pady=30)

class TransferFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#fef3c7", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Background
        bg_layer = ctk.CTkFrame(self, fg_color=("#fde68a", "#78350f"), corner_radius=0)
        bg_layer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, 
                                 width=550, height=650, border_width=2,
                                 border_color=("#fef3c7", "#334155"))
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Icon header
        icon_frame = ctk.CTkFrame(container, fg_color=("#f59e0b", "#d97706"), 
                                  corner_radius=20, height=100, width=100)
        icon_frame.pack(pady=(40, 20))
        
        icon_label = ctk.CTkLabel(icon_frame, text="🔄", font=ctk.CTkFont(size=50))
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="Transfer Money", 
                            font=ctk.CTkFont(size=38, weight="bold"), 
                            text_color=("#f59e0b", "#fbbf24"))
        title.pack(pady=(10, 5))

        subtitle = ctk.CTkLabel(container, text="Send money securely to another account", 
                               font=ctk.CTkFont(size=14), 
                               text_color=("#64748b", "#94a3b8"))
        subtitle.pack(pady=(0, 40))

        # Recipient Account
        recipient_label = ctk.CTkLabel(container, text="Recipient Account Number", 
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=("#475569", "#cbd5e1"))
        recipient_label.pack(anchor="w", padx=100, pady=(0, 8))
        
        self.recipient_entry = ctk.CTkEntry(container, 
                                           placeholder_text="Enter 10-digit account number", 
                                           width=350, height=50,
                                           font=ctk.CTkFont(size=15), corner_radius=12,
                                           border_width=2, border_color=("#e2e8f0", "#334155"))
        self.recipient_entry.pack(pady=(0, 25))

        # Amount
        amount_label = ctk.CTkLabel(container, text="Amount to Transfer", 
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   text_color=("#475569", "#cbd5e1"))
        amount_label.pack(anchor="w", padx=100, pady=(0, 8))
        
        self.amount_entry = ctk.CTkEntry(container, placeholder_text="Enter amount in ₹", 
                                        width=350, height=50,
                                        font=ctk.CTkFont(size=15), corner_radius=12,
                                        border_width=2, border_color=("#e2e8f0", "#334155"))
        self.amount_entry.pack(pady=(0, 35))
        self.amount_entry.bind("<Return>", lambda e: self.transfer_event())

        # Transfer Button
        self.transfer_button = AnimatedButton(container, text="Transfer Now →", 
                                             command=self.transfer_event,
                                             width=350, height=55, 
                                             font=ctk.CTkFont(size=17, weight="bold"),
                                             corner_radius=12, fg_color=("#f59e0b", "#d97706"),
                                             hover_color=("#d97706", "#b45309"))
        self.transfer_button.pack(pady=(0, 20))

        # Back Button
        back_btn = AnimatedButton(container, text="← Cancel", 
                                 command=self.master.show_dashboard_frame,
                                 width=350, height=48, fg_color="transparent", 
                                 border_width=2,
                                 border_color=("#f59e0b", "#fbbf24"), 
                                 text_color=("#f59e0b", "#fbbf24"),
                                 corner_radius=12, hover_color=("#fef3c7", "#1e293b"),
                                 font=ctk.CTkFont(size=15, weight="bold"))
        back_btn.pack(pady=(0, 40))

    def transfer_event(self):
        recipient = self.recipient_entry.get().strip()
        amount = self.amount_entry.get().strip()

        if not recipient or not amount:
            messagebox.showerror("Error", "Please fill all fields")
            return

        # Disable button during processing
        self.transfer_button.configure(state="disabled", text="Processing...")
        self.update()

        success, msg = self.master.controller.transfer(recipient, amount)
        
        self.transfer_button.configure(state="normal", text="Transfer Now →")
        
        if success:
            messagebox.showinfo("Success! 🎉", msg)
            self.recipient_entry.delete(0, 'end')
            self.amount_entry.delete(0, 'end')
            self.master.show_dashboard_frame()
        else:
            messagebox.showerror("Transfer Failed", msg)

class AccountDetailsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#e0f2fe", "#0f172a"))
        self.master = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Background
        bg_layer = ctk.CTkFrame(self, fg_color=("#bae6fd", "#0c4a6e"), corner_radius=0)
        bg_layer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main container
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, 
                                 width=550, height=700, border_width=2,
                                 border_color=("#e0f2fe", "#334155"))
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Profile icon
        profile_frame = ctk.CTkFrame(container, fg_color=("#06b6d4", "#0891b2"), 
                                     corner_radius=20, height=100, width=100)
        profile_frame.pack(pady=(40, 20))
        
        profile_icon = ctk.CTkLabel(profile_frame, text="👤", font=ctk.CTkFont(size=50))
        profile_icon.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title = ctk.CTkLabel(container, text="Account Details", 
                            font=ctk.CTkFont(size=38, weight="bold"), 
                            text_color=("#06b6d4", "#22d3ee"))
        title.pack(pady=(10, 50))

        # Get account info
        info = self.master.controller.get_account_info()

        if info:
            # Info cards with modern design
            details = [
                ("👤", "Account Holder", info['name']),
                ("🔢", "Account Number", info['account_number']),
                ("💰", "Current Balance", f"₹{info['balance']:,}"),
                ("📅", "Member Since", str(info['created_at'])[:19] if info['created_at'] else "N/A")
            ]

            for icon, label, value in details:
                card = ctk.CTkFrame(container, fg_color=("#f0f9ff", "#0e7490"), 
                                   corner_radius=15, height=85)
                card.pack(fill="x", padx=50, pady=10)

                # Icon
                icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=28))
                icon_label.pack(side="left", padx=(20, 15), pady=20)

                # Text content
                text_frame = ctk.CTkFrame(card, fg_color="transparent")
                text_frame.pack(side="left", fill="both", expand=True, pady=20)

                ctk.CTkLabel(text_frame, text=label, font=ctk.CTkFont(size=12),
                            text_color=("#0891b2", "#67e8f9")).pack(anchor="w")
                ctk.CTkLabel(text_frame, text=value, font=ctk.CTkFont(size=17, weight="bold"),
                            text_color=("#0c4a6e", "#cffafe")).pack(anchor="w", pady=(3, 0))

        # Back Button
        back_btn = AnimatedButton(container, text="← Back to Dashboard", 
                                 command=self.master.show_dashboard_frame,
                                 width=350, height=50, fg_color=("#06b6d4", "#0891b2"),
                                 hover_color=("#0891b2", "#0e7490"), corner_radius=12,
                                 font=ctk.CTkFont(size=15, weight="bold"))
        back_btn.pack(pady=(30, 40))

if __name__ == "__main__":
    app = BankApp()
    app.mainloop()
