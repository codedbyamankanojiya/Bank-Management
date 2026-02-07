import sqlite3
import random
import os
import csv
from tkinter import messagebox, filedialog
from datetime import datetime
import customtkinter as ctk
# Pillow is optional but good to have imported for potential future use or if installed
try:
    from PIL import Image
except ImportError:
    pass

# --- Backend Logic (Unchanged) ---
class DatabaseManager:
    def __init__(self, db_name="bank.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
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
        
    def get_user_by_name_and_pin(self, name, pin):
        self.cursor.execute("SELECT account_number FROM users WHERE name = ? AND pin = ?", (name, pin))
        result = self.cursor.fetchone()
        return result[0] if result else None

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
    
    def get_recent_recipients(self, user_id, limit=5):
        self.cursor.execute("""
            SELECT DISTINCT recipient_account, description 
            FROM transactions 
            WHERE user_id = ? AND type = 'TRANSFER_OUT'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        return self.cursor.fetchall()
    
    def get_analytics_data(self, user_id):
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
            
            if not sender or not recipient: return False, "Account not found"
            if sender[4] < amount: return False, "Insufficient balance"
            
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
        if not name or len(pin) != 4 or not pin.isdigit(): return "Invalid Input. Pin must be 4 digits."
        account_number = str(random.randint(1000000000, 9999999999))
        if self.db.create_user(name, pin, account_number): 
            return f"Account Created Successfully!\n\nYour Account Number is:\n{account_number}\n\nPLEASE SAVE THIS NUMBER NOW."
        else: return "Error creating account. Try again."

    def recover_account(self, name, pin):
        acc_num = self.db.get_user_by_name_and_pin(name, pin)
        if acc_num:
            return True, f"Identity Verified!\n\nYour Account Number is:\n{acc_num}"
        return False, "Verification Failed.\nName or PIN is incorrect."

    def sign_in(self, account_number, pin):
        user = self.db.get_user_by_account(account_number)
        if user:
            if user[2] == pin:
                self.current_user = {
                    "id": user[0], "name": user[1], "account_number": user[3],
                    "balance": user[4], "created_at": user[5] if len(user) > 5 else None
                }
                return True, f"Welcome {user[1]}"
            else: return False, "Incorrect PIN"
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
        
    def get_recent_recipients(self):
        if not self.current_user: return []
        return self.db.get_recent_recipients(self.current_user["id"])

    def get_analytics(self):
        if not self.current_user: return {"income": 0, "expense": 0}
        data = self.db.get_analytics_data(self.current_user["id"])
        income = sum(amt for type_, amt in data if type_ in ["DEPOSIT", "TRANSFER_IN"])
        expense = sum(amt for type_, amt in data if type_ in ["WITHDRAW", "TRANSFER_OUT"])
        return {"income": income, "expense": expense}
    
    def change_pin(self, old_pin, new_pin):
        if not self.current_user: return False, "Not logged in"
        user = self.db.get_user_by_id(self.current_user["id"])
        if user[2] != old_pin: return False, "Incorrect old PIN"
        if len(new_pin) != 4 or not new_pin.isdigit(): return False, "New PIN must be 4 digits"
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
        except Exception as e: return False, str(e)

    def get_account_info(self):
        if not self.current_user: return None
        return {
            "name": self.current_user["name"], "account_number": self.current_user["account_number"],
            "balance": self.current_user["balance"], "created_at": self.current_user.get("created_at", "N/A")
        }

    def get_balance(self): return self.current_user["balance"] if self.current_user else 0
    def logout(self): self.current_user = None

# --- UI Setup ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ToastNotification(ctk.CTkToplevel):
    def __init__(self, master, message, type="info"):
        super().__init__(master)
        self.overrideredirect(True)
        # Simplify geometry calculation to avoid errors
        try:
            x = master.winfo_x() + (master.winfo_width() // 2) - 150
            y = master.winfo_y() + 60
            self.geometry(f"300x50+{x}+{y}")
        except:
            # Fallback if master geometry is not ready
            self.geometry("300x50+100+100")
            
        self.attributes("-topmost", True)
        
        colors = {"success": "#10b981", "error": "#ef4444", "info": "#3b82f6"}
        bg_color = colors.get(type, "#3b82f6")
        
        self.frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=10)
        self.frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(self.frame, text=message, text_color="white", font=("Arial", 14, "bold"), wraplength=280).pack(pady=12, padx=15)
        
        self.after(3000, self.destroy)

class RecoveryDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Recover Account")
        self.geometry("400x350")
        self.resizable(False, False)
        
        # Center the window
        try:
            x = master.winfo_x() + (master.winfo_width() // 2) - 200
            y = master.winfo_y() + (master.winfo_height() // 2) - 175
            self.geometry(f"400x350+{x}+{y}")
        except: pass

        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="Recover Account Number", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        ctk.CTkLabel(self, text="Enter your details to verify identity", text_color="gray").pack(pady=(0, 20))
        
        self.name = create_styled_entry(self, "Full Name", width=300)
        self.name.pack(pady=10)
        
        self.pin = create_styled_entry(self, "4-Digit PIN", show="●", width=300)
        self.pin.pack(pady=10)
        
        AnimatedButton(self, text="Recover Account", command=self.recover, width=300, fg_color="#4f46e5").pack(pady=20)
        
    def recover(self):
        name = self.name.get()
        pin = self.pin.get()
        success, msg = self.master.master.controller.recover_account(name, pin)
        if success:
            messagebox.showinfo("Identity Verified", msg)
            self.destroy()
        else:
            messagebox.showerror("Failed", msg)

# Removed MobileEntry to fix layout issues. Using standard styled CTkEntry via helper.
def create_styled_entry(master, placeholder, show=None, width=300):
    return ctk.CTkEntry(master, placeholder_text=placeholder, show=show, width=width, height=45, font=("Arial", 14), corner_radius=10)

class AnimatedButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    def on_enter(self, event): self.configure(cursor="hand2")
    def on_leave(self, event): self.configure(cursor="")

class VirtualCard(ctk.CTkFrame):
    def __init__(self, master, name, account_num, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.card = ctk.CTkFrame(self, fg_color=("#4f46e5", "#3730a3"), corner_radius=20, height=220, width=380)
        self.card.pack(fill="both", expand=True)
        self.card.pack_propagate(False)
        
        gradient = ctk.CTkFrame(self.card, fg_color=("#6366f1", "#4338ca"), corner_radius=20, height=220, width=150)
        gradient.place(relx=0, rely=0)
        
        ctk.CTkFrame(self.card, fg_color="#fbbf24", width=50, height=35, corner_radius=5).place(relx=0.1, rely=0.25)
        ctk.CTkLabel(self.card, text=")))", font=("Arial", 20, "bold"), text_color="white").place(relx=0.85, rely=0.25, anchor="center")
        ctk.CTkLabel(self.card, text="SECURE BANK", font=("Arial", 14, "bold"), text_color="#e0e7ff").place(relx=0.9, rely=0.1, anchor="ne")
        
        masked_num = f"**** **** **** {account_num[-4:]}"
        ctk.CTkLabel(self.card, text=masked_num, font=("Courier New", 22, "bold"), text_color="white").place(relx=0.1, rely=0.55)
        ctk.CTkLabel(self.card, text=name.upper(), font=("Arial", 16, "bold"), text_color="white").place(relx=0.1, rely=0.82)
        ctk.CTkLabel(self.card, text="12/29", font=("Arial", 14, "bold"), text_color="white").place(relx=0.7, rely=0.82)

class BankApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.controller = BankController()
        self.title("SecureBank Pro - Stable")
        self.geometry("1300x850")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar_frame = None
        self.content_frame = None
        
        self.show_login_frame()

    def show_toast(self, message, type="info"):
        ToastNotification(self, message, type)

    def create_sidebar(self):
        if self.sidebar_frame: self.sidebar_frame.destroy()
        
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=("#f1f5f9", "#1e293b"))
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar_frame, text="🏦 SecureBank", font=ctk.CTkFont(size=24, weight="bold"), text_color=("#4f46e5", "#818cf8")).pack(pady=(40, 5))
        ctk.CTkLabel(self.sidebar_frame, text="PREMIUM", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(pady=(0, 40))
        
        self.nav_buttons = {}
        buttons = [
            ("📊 Dashboard", self.show_dashboard_frame),
            ("💸 Transfer", self.show_transfer_frame),
            ("📜 History", self.show_history_frame),
            ("📈 Analytics", self.show_analytics_frame),
            ("⚙️ Settings", self.show_settings_frame),
        ]
        
        for text, cmd in buttons:
            btn = AnimatedButton(self.sidebar_frame, text=text, command=lambda c=cmd, t=text: self.nav_click(c, t), 
                          fg_color="transparent", text_color=("#1e293b", "#e2e8f0"),
                          hover_color=("#e2e8f0", "#334155"), anchor="w", 
                          width=220, height=45, font=ctk.CTkFont(size=16))
            btn.pack(pady=5)
            self.nav_buttons[text] = btn
            
        AnimatedButton(self.sidebar_frame, text="🚪 Logout", command=self.logout_event,
                      fg_color=("#fee2e2", "#7f1d1d"), hover_color=("#fecaca", "#991b1b"),
                      text_color=("#dc2626", "#fca5a5"), width=200).pack(side="bottom", pady=30)

    def nav_click(self, cmd, text):
        for name, btn in self.nav_buttons.items():
            if name == text:
                btn.configure(fg_color=("#e0e7ff", "#312e81"), text_color=("#4338ca", "#818cf8"))
            else:
                btn.configure(fg_color="transparent", text_color=("#1e293b", "#e2e8f0"))
        cmd()

    def switch_frame(self, frame_class, **kwargs):
        # Simplified switch logic: removing animation to prevent layout issues
        if self.content_frame: self.content_frame.destroy()
        self.content_frame = frame_class(self, **kwargs)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def show_login_frame(self):
        if self.sidebar_frame: 
            self.sidebar_frame.destroy()
            self.sidebar_frame = None
        
        # Ensure cleanup
        if self.content_frame: self.content_frame.destroy()
        
        self.content_frame = LoginFrame(self)
        self.content_frame.grid(row=0, column=0, columnspan=2, sticky="nsew") # Span both to ensure full width
        
        # Reset weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

    def show_dashboard_frame(self): self.setup_main_view(); self.switch_frame(DashboardFrame); self.nav_click(lambda: None, "📊 Dashboard")
    def show_transfer_frame(self): self.setup_main_view(); self.switch_frame(TransferFrame); self.nav_click(lambda: None, "💸 Transfer")
    def show_history_frame(self): self.setup_main_view(); self.switch_frame(HistoryFrame); self.nav_click(lambda: None, "📜 History")
    def show_analytics_frame(self): self.setup_main_view(); self.switch_frame(AnalyticsFrame); self.nav_click(lambda: None, "📈 Analytics")
    def show_settings_frame(self): self.setup_main_view(); self.switch_frame(SettingsFrame); self.nav_click(lambda: None, "⚙️ Settings")

    def setup_main_view(self):
        if not self.sidebar_frame: self.create_sidebar()
        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)

    def logout_event(self):
        if messagebox.askyesno("Logout", "Are you sure?"):
            self.controller.logout()
            self.show_login_frame()

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#e0e7ff", "#0f172a"))
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, width=400, height=550)
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(container, text="🏦 SecureBank", font=ctk.CTkFont(size=32, weight="bold")).pack(pady=(40, 20))
        
        self.acc_entry = create_styled_entry(container, "Account Number", width=300)
        self.acc_entry.pack(pady=10)
        
        self.pin_entry = create_styled_entry(container, "PIN", show="●", width=300)
        self.pin_entry.pack(pady=10)
        
        AnimatedButton(container, text="Sign In", command=self.login_event, width=300, height=45, fg_color="#4f46e5", hover_color="#4338ca").pack(pady=20)
        
        # Forgot Account link
        AnimatedButton(container, text="Forgot Account Number?", command=self.show_recovery, fg_color="transparent", text_color="gray", height=20, font=("Arial", 12)).pack(pady=(0, 20))
        
        AnimatedButton(container, text="Create Account", command=self.show_register, fg_color="transparent", text_color="#4f46e5").pack()

    def login_event(self):
        acc = self.acc_entry.get()
        pin = self.pin_entry.get()
        success, msg = self.master.controller.sign_in(acc, pin)
        if success: 
            self.master.show_toast(msg, "success")
            self.master.show_dashboard_frame()
        else: 
            self.master.show_toast(msg, "error")

    def show_register(self):
        RegisterFrame(self.master).grid(row=0, column=0, columnspan=2, sticky="nsew")
        
    def show_recovery(self):
        RecoveryDialog(self)

class RegisterFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#dcfce7", "#0f172a"))
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=25, width=400, height=550)
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(container, text="Create Account", font=ctk.CTkFont(size=30, weight="bold")).pack(pady=30)
        self.name = create_styled_entry(container, "Full Name", width=300)
        self.name.pack(pady=10)
        self.pin = create_styled_entry(container, "4-Digit PIN", show="●", width=300)
        self.pin.pack(pady=10)
        AnimatedButton(container, text="Register", command=self.register, width=300, height=45, fg_color="#10b981", hover_color="#059669").pack(pady=30)
        AnimatedButton(container, text="Back to Login", command=master.show_login_frame, fg_color="transparent", text_color="#10b981").pack()

    def register(self):
        name = self.name.get()
        pin = self.pin.get()
        msg = self.master.controller.sign_up(name, pin)
        if "Created" in msg:
            # Persistent modal for successful registration
            messagebox.showinfo("Success - Save This!", msg)
            self.master.show_login_frame()
        else:
            self.master.show_toast(msg, "error")

class DashboardFrame(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.controller = master.controller
        user = self.controller.current_user
        
        ctk.CTkLabel(self, text=f"Hello, {user['name']} 👋", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w", pady=(0, 20))
        
        # Cards Row
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", pady=10)
        VirtualCard(row1, user['name'], user['account_number']).pack(side="left", padx=(0, 20))
        
        bal_frame = ctk.CTkFrame(row1, fg_color=("#ffffff", "#1e293b"), corner_radius=20, height=220)
        bal_frame.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(bal_frame, text="Current Balance", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray").pack(pady=(40, 10))
        ctk.CTkLabel(bal_frame, text=f"₹{self.controller.get_balance():,}", font=ctk.CTkFont(size=48, weight="bold"), text_color="#10b981").pack()
        
        # Quick Transfer Carousel
        ctk.CTkLabel(self, text="Recent People", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(30, 10))
        people_frame = ctk.CTkFrame(self, fg_color="transparent")
        people_frame.pack(fill="x", anchor="w")
        
        recipients = self.controller.get_recent_recipients()
        if recipients:
            for r_acc, desc in recipients:
                name = desc.replace("Transfer to ", "") if "Transfer to " in desc else "Unknown"
                initials = "".join([n[0] for n in name.split()[:2]]).upper()
                
                person = ctk.CTkFrame(people_frame, fg_color="transparent")
                person.pack(side="left", padx=10)
                
                avatar = AnimatedButton(person, text=initials, width=50, height=50, corner_radius=25, 
                                       fg_color="#6366f1", hover_color="#4f46e5", 
                                       command=lambda a=r_acc: self.quick_transfer(a))
                avatar.pack()
                ctk.CTkLabel(person, text=name, font=("Arial", 10)).pack()
        else:
            ctk.CTkLabel(people_frame, text="No recent transfers", text_color="gray").pack(anchor="w")

        # Layout: Recent Activity Widget & Quick Actions
        lower_row = ctk.CTkFrame(self, fg_color="transparent")
        lower_row.pack(fill="x", pady=30)
        
        # Recent Activity Widget
        activity_frame = ctk.CTkFrame(lower_row, fg_color=("#ffffff", "#1e293b"), corner_radius=20, width=500)
        activity_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))
        ctk.CTkLabel(activity_frame, text="Recent Activity", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=20)
        
        trans = self.controller.get_transaction_history(3)
        if trans:
            for t in trans:
                self.create_mini_trans(activity_frame, t)
        else:
            ctk.CTkLabel(activity_frame, text="No recent activity", text_color="gray").pack(pady=20)
            
        # Quick Actions
        actions_frame = ctk.CTkFrame(lower_row, fg_color=("#ffffff", "#1e293b"), corner_radius=20, width=300)
        actions_frame.pack(side="left", fill="both")
        ctk.CTkLabel(actions_frame, text="Quick Transaction", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=20)
        
        self.amount_entry = create_styled_entry(actions_frame, "Amount", width=250)
        self.amount_entry.pack(pady=10, padx=20)
        
        btns = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btns.pack(pady=10)
        AnimatedButton(btns, text="Deposit", command=self.deposit, fg_color="#10b981", width=120).pack(side="left", padx=5)
        AnimatedButton(btns, text="Withdraw", command=self.withdraw, fg_color="#ef4444", width=120).pack(side="left", padx=5)
        
    def create_mini_trans(self, master, t):
        type_, amt, _, time, _ = t
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        color = "#10b981" if type_ in ["DEPOSIT", "TRANSFER_IN"] else "#ef4444"
        ctk.CTkLabel(row, text=type_.replace("_", " "), font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(row, text=f"₹{amt:,}", font=("Arial", 12, "bold"), text_color=color).pack(side="right")
        
    def deposit(self):
        amt = self.amount_entry.get()
        success, msg = self.controller.deposit(amt)
        self.master.show_toast(msg, "success" if success else "error")
        if success: self.master.show_dashboard_frame()
        
    def withdraw(self):
        amt = self.amount_entry.get()
        success, msg = self.controller.withdraw(amt)
        self.master.show_toast(msg, "success" if success else "error")
        if success: self.master.show_dashboard_frame()

    def quick_transfer(self, acc):
        self.master.show_transfer_frame()
        self.master.content_frame.set_recipient(acc)

class TransferFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=20)
        container.pack(fill="both", expand=True, padx=50, pady=50)
        
        ctk.CTkLabel(container, text="Transfer Money", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=40)
        self.recip = create_styled_entry(container, "Recipient Account Number", width=400)
        self.recip.pack(pady=20)
        self.amt = create_styled_entry(container, "Amount (₹)", width=400)
        self.amt.pack(pady=20)
        AnimatedButton(container, text="Send Money", command=self.send, width=400, height=50, fg_color="#4f46e5").pack(pady=40)
        
    def send(self):
        success, msg = self.master.controller.transfer(self.recip.get(), self.amt.get())
        self.master.show_toast(msg, "success" if success else "error")
        if success: self.master.show_dashboard_frame()
        
    def set_recipient(self, acc):
        self.recip.delete(0, 'end')
        self.recip.insert(0, acc)

class HistoryFrame(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=20)
        ctk.CTkLabel(header, text="Transaction History", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        AnimatedButton(header, text="📥 Export CSV", command=self.export_csv, width=120, fg_color="#64748b").pack(side="right")
        trans = master.controller.get_transaction_history()
        for t in trans: self.create_trans_row(t)
            
    def create_trans_row(self, t):
        type_, amt, recip, time, desc = t
        color = "#10b981" if type_ in ["DEPOSIT", "TRANSFER_IN"] else "#ef4444"
        row = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=10, height=60)
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="⬇" if "IN" in type_ or "DEPOSIT" in type_ else "⬆", font=("Arial", 20), text_color=color).pack(side="left", padx=20)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=desc if desc else type_, font=("Arial", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(info, text=time, font=("Arial", 10), text_color="gray").pack(anchor="w")
        ctk.CTkLabel(row, text=f"₹{amt:,}", font=("Arial", 16, "bold"), text_color=color).pack(side="right", padx=20)

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filename:
            success, msg = self.master.controller.export_history_csv(filename)
            self.master.show_toast(msg, "success" if success else "error")

class AnalyticsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Financial Insights", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=20)
        data = master.controller.get_analytics()
        income, expense = data['income'], abs(data['expense'])
        total = income + expense if (income + expense) > 0 else 1
        
        container = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=20)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        for label, val, col in [("Total Income", income, "#10b981"), ("Total Expenses", expense, "#ef4444")]:
            ctk.CTkLabel(container, text=label, text_color=col).pack(anchor="w", padx=20, pady=(20, 5))
            bar = ctk.CTkProgressBar(container, progress_color=col, height=20)
            bar.pack(fill="x", padx=20)
            bar.set(val / total)
            ctk.CTkLabel(container, text=f"₹{val:,}", font=("Arial", 16, "bold")).pack(anchor="w", padx=20)

class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=20)
        
        theme_frame = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=15)
        theme_frame.pack(fill="x", pady=10, ipady=10)
        ctk.CTkLabel(theme_frame, text="Dark Mode", font=("Arial", 16, "bold")).pack(side="left", padx=20)
        self.switch = ctk.CTkSwitch(theme_frame, text="", command=self.toggle_theme)
        if ctk.get_appearance_mode() == "Dark": self.switch.select()
        self.switch.pack(side="right", padx=20)
        
        pin_frame = ctk.CTkFrame(self, fg_color=("#ffffff", "#1e293b"), corner_radius=15)
        pin_frame.pack(fill="x", pady=10, ipady=20)
        ctk.CTkLabel(pin_frame, text="Change PIN", font=("Arial", 16, "bold")).pack(anchor="w", padx=20, pady=10)
        
        self.old = create_styled_entry(pin_frame, "Old PIN", show="●", width=300)
        self.old.pack(pady=5)
        self.new = create_styled_entry(pin_frame, "New PIN", show="●", width=300)
        self.new.pack(pady=5)
        AnimatedButton(pin_frame, text="Update", command=self.update_pin, fg_color="#f59e0b").pack(pady=10)

    def toggle_theme(self): ctk.set_appearance_mode("Dark" if self.switch.get() else "Light")
    def update_pin(self):
        success, msg = self.master.controller.change_pin(self.old.get(), self.new.get())
        self.master.show_toast(msg, "success" if success else "error")

if __name__ == "__main__":
    app = BankApp()
    app.mainloop()
