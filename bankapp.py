import sqlite3
import random
import os
import csv
from tkinter import messagebox, filedialog
from datetime import datetime
import customtkinter as ctk
from PIL import Image

# Enhanced Database Manager to support new features
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
    
    def get_user_by_id(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return self.cursor.fetchone()

    def update_balance(self, account_number, new_balance):
        self.cursor.execute("UPDATE users SET balance = ? WHERE account_number = ?", (new_balance, account_number))
        self.conn.commit()
        
    def update_pin(self, user_id, new_pin):
        self.cursor.execute("UPDATE users SET pin = ? WHERE id = ?", (new_pin, user_id))
        self.conn.commit()
        return True

    def add_transaction(self, user_id, trans_type, amount, recipient_account=None, description=None):
        self.cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, recipient_account, description)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, trans_type, amount, recipient_account, description))
        self.conn.commit()

    def get_transaction_history(self, user_id, limit=100):
        self.cursor.execute("""
            SELECT type, amount, recipient_account, timestamp, description
            FROM transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        return self.cursor.fetchall()
    
    def get_analytics_data(self, user_id):
        # Get total income (Deposit + Transfer In) and expenses (Withdraw + Transfer Out)
        self.cursor.execute("""
            SELECT type, SUM(amount) 
            FROM transactions 
            WHERE user_id = ? 
            GROUP BY type
        """, (user_id,))
        return self.cursor.fetchall()

    def transfer_money(self, from_account, to_account, amount):
        try:
            sender = self.get_user_by_account(from_account)
            recipient = self.get_user_by_account(to_account)
            
            if not sender or not recipient:
                return False, "Account not found"
            
            if sender[4] < amount:
                return False, "Insufficient balance"
            
            new_sender_balance = sender[4] - amount
            new_recipient_balance = recipient[4] + amount
            
            self.update_balance(from_account, new_sender_balance)
            self.update_balance(to_account, new_recipient_balance)
            
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
        if not self.current_user: return False, "Not logged in"
        try:
            amount = int(amount)
            if amount <= 0: return False, "Amount must be positive"
            
            new_balance = self.current_user["balance"] + amount
            self.db.update_balance(self.current_user["account_number"], new_balance)
            self.current_user["balance"] = new_balance
            self.db.add_transaction(self.current_user["id"], "DEPOSIT", amount, description="Deposit")
            return True, f"Deposited ₹{amount}. New Balance: ₹{new_balance}"
        except ValueError: return False, "Invalid amount"

    def withdraw(self, amount):
        if not self.current_user: return False, "Not logged in"
        try:
            amount = int(amount)
            if amount <= 0: return False, "Amount must be positive"
            if self.current_user["balance"] < amount: return False, "Insufficient Balance"
            
            new_balance = self.current_user["balance"] - amount
            self.db.update_balance(self.current_user["account_number"], new_balance)
            self.current_user["balance"] = new_balance
            self.db.add_transaction(self.current_user["id"], "WITHDRAW", amount, description="Withdrawal")
            return True, f"Withdrew ₹{amount}. New Balance: ₹{new_balance}"
        except ValueError: return False, "Invalid amount"

    def transfer(self, recipient_account, amount):
        if not self.current_user: return False, "Not logged in"
        try:
            amount = int(amount)
            if amount <= 0: return False, "Amount must be positive"
            if recipient_account == self.current_user["account_number"]: return False, "Cannot transfer to self"
            
            success, message = self.db.transfer_money(self.current_user["account_number"], recipient_account, amount)
            if success:
                user = self.db.get_user_by_account(self.current_user["account_number"])
                self.current_user["balance"] = user[4]
            return success, message
        except ValueError: return False, "Invalid amount"

    def get_transaction_history(self, limit=100):
        if not self.current_user: return []
        return self.db.get_transaction_history(self.current_user["id"], limit)

    def get_analytics(self):
        if not self.current_user: return {"income": 0, "expense": 0}
        data = self.db.get_analytics_data(self.current_user["id"])
        income = sum(amt for type_, amt in data if type_ in ["DEPOSIT", "TRANSFER_IN"])
        expense = sum(amt for type_, amt in data if type_ in ["WITHDRAW", "TRANSFER_OUT"])
        return {"income": income, "expense": expense}
    
    def change_pin(self, old_pin, new_pin):
        if not self.current_user: return False, "Not logged in"
        
        # Verify old pin by re-fetching user
        user = self.db.get_user_by_id(self.current_user["id"])
        if user[2] != old_pin:
            return False, "Incorrect old PIN"
        
        if len(new_pin) != 4 or not new_pin.isdigit():
            return False, "New PIN must be 4 digits"
            
        self.db.update_pin(self.current_user["id"], new_pin)
        return True, "PIN updated successfully"

    def export_history_csv(self, file_path):
        if not self.current_user: return False, "Not logged in"
        transactions = self.get_transaction_history(1000)
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Type", "Amount", "Recipient/Sender", "Date", "Description"])
                writer.writerows(transactions)
            return True, "Export successful"
        except Exception as e:
            return False, str(e)

    def get_account_info(self):
        if not self.current_user: return None
        return {
            "name": self.current_user["name"],
            "account_number": self.current_user["account_number"],
            "balance": self.current_user["balance"],
            "created_at": self.current_user.get("created_at", "N/A")
        }

    def get_balance(self):
        return self.current_user["balance"] if self.current_user else 0

    def logout(self):
        self.current_user = None

# UI Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AnimatedButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    def on_enter(self, event): self.configure(cursor="hand2")
    def on_leave(self, event): self.configure(cursor="")

class VirtualCard(ctk.CTkFrame):
    def __init__(self, master, name, account_num, **kwargs):
        super().__init__(master, **kwargs)
        
        # Platinum Gradient Background
        self.configure(fg_color=("#1e293b", "#0f172a")) # Fallback
        
        # Card Graphic Container
        self.card = ctk.CTkFrame(self, fg_color=("#4f46e5", "#3730a3"), corner_radius=20, height=220, width=380)
        self.card.pack(fill="both", expand=True)
        self.card.pack_propagate(False)
        
        # Gradient overlay simulation
        gradient = ctk.CTkFrame(self.card, fg_color=("#6366f1", "#4338ca"), corner_radius=20, height=220, width=150)
        gradient.place(relx=0, rely=0)
        
        # Chip
        chip = ctk.CTkFrame(self.card, fg_color="#fbbf24", width=50, height=35, corner_radius=5)
        chip.place(relx=0.1, rely=0.25)
        
        # Contactless Icon
        ctk.CTkLabel(self.card, text=")))", font=("Arial", 20, "bold"), text_color="white").place(relx=0.85, rely=0.25, anchor="center")
        
        # Bank Name
        ctk.CTkLabel(self.card, text="SECURE BANK", font=("Arial", 14, "bold"), text_color="#e0e7ff").place(relx=0.9, rely=0.1, anchor="ne")
        
        # Account Number (Masked)
        masked_num = f"**** **** **** {account_num[-4:]}"
        ctk.CTkLabel(self.card, text=masked_num, font=("Courier New", 22, "bold"), text_color="white").place(relx=0.1, rely=0.55)
        
        # Card Holder Name
        ctk.CTkLabel(self.card, text="CARD HOLDER", font=("Arial", 10), text_color="#c7d2fe").place(relx=0.1, rely=0.75)
        ctk.CTkLabel(self.card, text=name.upper(), font=("Arial", 16, "bold"), text_color="white").place(relx=0.1, rely=0.82)
        
        # Expiry
        ctk.CTkLabel(self.card, text="VALID THRU", font=("Arial", 8), text_color="#c7d2fe").place(relx=0.7, rely=0.75)
        ctk.CTkLabel(self.card, text="12/29", font=("Arial", 14, "bold"), text_color="white").place(relx=0.7, rely=0.82)

class BankApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.controller = BankController()
        self.title("SecureBank Pro - Advanced")
        self.geometry("1300x850")
        
        # Main Layout: 2 Columns (Sidebar + Content)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar_frame = None
        self.content_frame = None
        
        self.show_login_frame()

    def create_sidebar(self):
        if self.sidebar_frame: self.sidebar_frame.destroy()
        
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=("#f1f5f9", "#1e293b"))
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # App Logo
        ctk.CTkLabel(self.sidebar_frame, text="🏦 SecureBank", font=ctk.CTkFont(size=24, weight="bold"), text_color=("#4f46e5", "#818cf8")).pack(pady=(40, 10))
        ctk.CTkLabel(self.sidebar_frame, text="PRO EDITION", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(0, 40))
        
        # Navigation Buttons
        buttons = [
            ("📊 Dashboard", self.show_dashboard_frame),
            ("💸 Transfer", self.show_transfer_frame),
            ("📜 History", self.show_history_frame),
            ("📈 Analytics", self.show_analytics_frame),
            ("⚙️ Settings", self.show_settings_frame),
        ]
        
        for text, cmd in buttons:
            AnimatedButton(self.sidebar_frame, text=text, command=cmd, 
                          fg_color="transparent", text_color=("#1e293b", "#e2e8f0"),
                          hover_color=("#e2e8f0", "#334155"), anchor="w", 
                          width=220, height=45, font=ctk.CTkFont(size=16)).pack(pady=5)
                          
        # Spacer
        ctk.CTkFrame(self.sidebar_frame, fg_color="transparent").pack(expand=True, fill="both")
        
        # Logout
        AnimatedButton(self.sidebar_frame, text="🚪 Logout", command=self.logout_event,
                      fg_color=("#fee2e2", "#7f1d1d"), hover_color=("#fecaca", "#991b1b"),
                      text_color=("#dc2626", "#fca5a5"), width=200).pack(pady=30)

    def switch_frame(self, frame_class, **kwargs):
        if self.content_frame: self.content_frame.destroy()
        self.content_frame = frame_class(self, **kwargs)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def show_login_frame(self):
        if self.sidebar_frame: 
            self.sidebar_frame.destroy()
            self.sidebar_frame = None
        self.switch_frame(LoginFrame)
        # Reset grid to 1 column for login
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.content_frame.grid(row=0, column=0, sticky="nsew")

    def show_dashboard_frame(self):
        self.setup_main_view()
        self.switch_frame(DashboardFrame)

    def show_transfer_frame(self):
        self.setup_main_view()
        self.switch_frame(TransferFrame)

    def show_history_frame(self):
        self.setup_main_view()
        self.switch_frame(HistoryFrame)

    def show_analytics_frame(self):
        self.setup_main_view()
        self.switch_frame(AnalyticsFrame)

    def show_settings_frame(self):
        self.setup_main_view()
        self.switch_frame(SettingsFrame)

    def setup_main_view(self):
        # Configure grid for sidebar + content
        self.grid_columnconfigure(0, weight=0) # Sidebar fixed
        self.grid_columnconfigure(1, weight=1) # Content expands
        if not self.sidebar_frame: self.create_sidebar()

    def logout_event(self):
        if messagebox.askyesno("Logout", "Are you sure?"):
            self.controller.logout()
            self.show_login_frame()

# --- FRAMES ---

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#e0e7ff", "#0f172a"))
        
        # Simplified for brevity (Keeping the modern look from prev version)
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, width=400, height=500)
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(container, text="🏦 SecureBank", font=ctk.CTkFont(size=32, weight="bold")).pack(pady=40)
        
        self.acc_entry = ctk.CTkEntry(container, placeholder_text="Account Number", width=300, height=45)
        self.acc_entry.pack(pady=10)
        
        self.pin_entry = ctk.CTkEntry(container, placeholder_text="PIN", show="●", width=300, height=45)
        self.pin_entry.pack(pady=10)
        
        AnimatedButton(container, text="Sign In", command=self.login_event, width=300, height=45, fg_color="#4f46e5", hover_color="#4338ca").pack(pady=20)
        
        AnimatedButton(container, text="Create Account", command=self.show_register, fg_color="transparent", text_color="#4f46e5").pack()

    def login_event(self):
        acc = self.acc_entry.get()
        pin = self.pin_entry.get()
        success, msg = self.master.controller.sign_in(acc, pin)
        if success: self.master.show_dashboard_frame()
        else: messagebox.showerror("Error", msg)

    def show_register(self):
        RegisterFrame(self.master).grid(row=0, column=0, sticky="nsew")

class RegisterFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#dcfce7", "#0f172a"))
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25)
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(container, text="Create Account", font=ctk.CTkFont(size=30, weight="bold")).pack(pady=30, padx=50)
        
        self.name = ctk.CTkEntry(container, placeholder_text="Full Name", width=300)
        self.name.pack(pady=10)
        
        self.pin = ctk.CTkEntry(container, placeholder_text="4-Digit PIN", show="●", width=300)
        self.pin.pack(pady=10)
        
        AnimatedButton(container, text="Register", command=self.register, width=300, fg_color="#10b981", hover_color="#059669").pack(pady=20)
        AnimatedButton(container, text="Back to Login", command=master.show_login_frame, fg_color="transparent", text_color="#10b981").pack(pady=10)

    def register(self):
        name = self.name.get()
        pin = self.pin.get()
        msg = self.master.controller.sign_up(name, pin)
        if "Created" in msg:
            messagebox.showinfo("Success", msg)
            self.master.show_login_frame()
        else:
            messagebox.showerror("Error", msg)

class DashboardFrame(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.controller = master.controller
        
        # Header
        user = self.controller.current_user
        ctk.CTkLabel(self, text=f"Hello, {user['name']} 👋", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w", pady=(0, 20))
        
        # Top Stats Row
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", pady=10)
        
        # Virtual Card (Left)
        card = VirtualCard(row1, user['name'], user['account_number'])
        card.pack(side="left", padx=(0, 20))
        
        # Balance Card (Right)
        bal_frame = ctk.CTkFrame(row1, fg_color=("#ffffff", "#1e293b"), corner_radius=20, height=220)
        bal_frame.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(bal_frame, text="Current Balance", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray").pack(pady=(40, 10))
        ctk.CTkLabel(bal_frame, text=f"₹{self.controller.get_balance():,}", font=ctk.CTkFont(size=48, weight="bold"), text_color="#10b981").pack()
        
        # Quick Actions
        ctk.CTkLabel(self, text="Quick Actions", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(30, 15))
        
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x")
        
        self.amount_entry = ctk.CTkEntry(actions, placeholder_text="Amount", width=200, height=40)
        self.amount_entry.pack(side="left", padx=(0, 10))
        
        AnimatedButton(actions, text="➕ Deposit", command=self.deposit, fg_color="#10b981", width=120).pack(side="left", padx=5)
        AnimatedButton(actions, text="➖ Withdraw", command=self.withdraw, fg_color="#ef4444", width=120).pack(side="left", padx=5)
        
    def deposit(self):
        amt = self.amount_entry.get()
        success, msg = self.controller.deposit(amt)
        self.handle_trans(success, msg)
        
    def withdraw(self):
        amt = self.amount_entry.get()
        success, msg = self.controller.withdraw(amt)
        self.handle_trans(success, msg)
        
    def handle_trans(self, success, msg):
        if success:
            messagebox.showinfo("Success", msg)
            self.master.show_dashboard_frame() # Refresh
        else:
            messagebox.showerror("Error", msg)

class AnalyticsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        ctk.CTkLabel(self, text="Financial Insights 📈", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=20)
        
        data = master.controller.get_analytics()
        income = data['income']
        expense = abs(data['expense'])
        total = income + expense if (income + expense) > 0 else 1
        
        # Charts Container
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=20)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Income Bar
        ctk.CTkLabel(container, text="Total Income", text_color="#10b981").pack(anchor="w", padx=20, pady=(20, 5))
        inc_bar = ctk.CTkProgressBar(container, progress_color="#10b981", height=20)
        inc_bar.pack(fill="x", padx=20)
        inc_bar.set(income / total)
        ctk.CTkLabel(container, text=f"₹{income:,}", font=("Arial", 16, "bold")).pack(anchor="w", padx=20)
        
        # Expense Bar
        ctk.CTkLabel(container, text="Total Expenses", text_color="#ef4444").pack(anchor="w", padx=20, pady=(30, 5))
        exp_bar = ctk.CTkProgressBar(container, progress_color="#ef4444", height=20)
        exp_bar.pack(fill="x", padx=20)
        exp_bar.set(expense / total)
        ctk.CTkLabel(container, text=f"₹{expense:,}", font=("Arial", 16, "bold")).pack(anchor="w", padx=20)
        
        # Summary
        savings = income - expense
        color = "#10b981" if savings >= 0 else "#ef4444"
        ctk.CTkLabel(container, text=f"Net Savings: ₹{savings:,}", font=("Arial", 24, "bold"), text_color=color).pack(pady=40)

class TransferFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=20)
        container.pack(fill="both", expand=True, padx=50, pady=50)
        
        ctk.CTkLabel(container, text="Transfer Money 💸", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=40)
        
        self.recip = ctk.CTkEntry(container, placeholder_text="Recipient Account Number", width=400, height=50)
        self.recip.pack(pady=20)
        
        self.amt = ctk.CTkEntry(container, placeholder_text="Amount (₹)", width=400, height=50)
        self.amt.pack(pady=20)
        
        AnimatedButton(container, text="Send Money", command=self.send, width=400, height=50, fg_color="#4f46e5").pack(pady=40)
        
    def send(self):
        success, msg = self.master.controller.transfer(self.recip.get(), self.amt.get())
        if success:
            messagebox.showinfo("Success", msg)
            self.master.show_dashboard_frame()
        else:
            messagebox.showerror("Error", msg)

class HistoryFrame(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # Header Row with Export
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=20)
        ctk.CTkLabel(header, text="Transaction History", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        AnimatedButton(header, text="📥 Export CSV", command=self.export_csv, width=120, fg_color="#64748b").pack(side="right")
        
        # List
        trans = master.controller.get_transaction_history()
        for t in trans:
            self.create_trans_row(t)
            
    def create_trans_row(self, t):
        type_, amt, recip, time, desc = t
        color = "#10b981" if type_ in ["DEPOSIT", "TRANSFER_IN"] else "#ef4444"
        icon = "⬇" if type_ in ["DEPOSIT", "TRANSFER_IN"] else "⬆"
        
        row = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=10, height=60)
        row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row, text=icon, font=("Arial", 20), text_color=color).pack(side="left", padx=20)
        
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=type_.replace("_", " "), font=("Arial", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(info, text=time, font=("Arial", 10), text_color="gray").pack(anchor="w")
        
        ctk.CTkLabel(row, text=f"₹{amt:,}", font=("Arial", 16, "bold"), text_color=color).pack(side="right", padx=20)

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filename:
            success, msg = self.master.controller.export_history_csv(filename)
            if success: messagebox.showinfo("Export", "History exported successfully!")

class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        ctk.CTkLabel(self, text="Settings ⚙️", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=20)
        
        # Theme Toggle
        theme_frame = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=15)
        theme_frame.pack(fill="x", pady=10, ipady=10)
        
        ctk.CTkLabel(theme_frame, text="Appearance Mode", font=("Arial", 16, "bold")).pack(side="left", padx=20)
        
        self.theme_switch = ctk.CTkSwitch(theme_frame, text="Dark Mode", command=self.toggle_theme)
        if ctk.get_appearance_mode() == "Dark": self.theme_switch.select()
        self.theme_switch.pack(side="right", padx=20)
        
        # Change PIN
        pin_frame = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=15)
        pin_frame.pack(fill="x", pady=10, ipady=20)
        
        ctk.CTkLabel(pin_frame, text="Security: Change PIN", font=("Arial", 16, "bold")).pack(anchor="w", padx=20, pady=10)
        
        self.old_pin = ctk.CTkEntry(pin_frame, placeholder_text="Old PIN", show="●")
        self.old_pin.pack(pady=5, padx=20, fill="x")
        
        self.new_pin = ctk.CTkEntry(pin_frame, placeholder_text="New PIN", show="●")
        self.new_pin.pack(pady=5, padx=20, fill="x")
        
        AnimatedButton(pin_frame, text="Update PIN", command=self.update_pin, fg_color="#f59e0b").pack(pady=10)
        
    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")
            
    def update_pin(self):
        success, msg = self.master.controller.change_pin(self.old_pin.get(), self.new_pin.get())
        if success:
            messagebox.showinfo("Success", msg)
            self.old_pin.delete(0, 'end')
            self.new_pin.delete(0, 'end')
        else:
            messagebox.showerror("Error", msg)

if __name__ == "__main__":
    app = BankApp()
    app.mainloop()
