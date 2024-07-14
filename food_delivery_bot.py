from decimal import Decimal
import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FoodDeliveryChatbot:
    def __init__(self):
        self.db_connection = self.connect_to_mysql()
        self.menu_items = self.fetch_menu()

    def connect_to_mysql(self):
        try:
            host = os.getenv("DB_HOST")
            user = os.getenv("DB_USER")
            password = os.getenv("DB_PASSWORD")
            database = os.getenv("DB_DATABASE")

            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            if conn.is_connected():
                print("Connected to MySQL database")
                return conn
            else:
                print("Failed to connect to MySQL database")
                return None
        except mysql.connector.Error as e:
            print(e)
            return None

    def fetch_menu(self):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT item_id, item_name, category, description, price FROM menu;")
            return cursor.fetchall()
        except mysql.connector.Error as e:
            print(f"Error fetching menu items: {e}")
            return []

    def display_menu(self):
        print("\nMenu:")
        for item in self.menu_items:
            print(f"{item[1]} - ₹{item[4]:.2f}")

    def create_order(self, customer_name, delivery_address, phone, order_details):
        try:
            cursor = self.db_connection.cursor()

            total_amount = Decimal('0.00')
            order_items = []

            for item_name, quantity in order_details.items():
                # Fetch item details by item_name
                cursor.execute("SELECT item_id, price FROM menu WHERE item_name = %s;", (item_name,))
                item = cursor.fetchone()

                if not item:
                    return f"Item '{item_name}' not found in the menu. Please check the item name and try again."

                item_id, price = item
                price = float(price)  # Convert Decimal price to float
                total_amount += Decimal(price * quantity)
                order_items.append((item_id, quantity))

            # Insert order into orders table
            cursor.execute("""
                INSERT INTO orders (customer_name, phone, delivery_address, total_amount, order_status)
                VALUES (%s, %s, %s, %s, 'Pending');
            """, (customer_name, phone, delivery_address, total_amount))
            self.db_connection.commit()

            order_id = cursor.lastrowid  # Get auto-generated order ID

            # Record transaction in transaction history
            cursor.execute("""
                INSERT INTO transaction_history (order_id, transaction_amount)
                VALUES (%s, %s);
            """, (order_id, total_amount))
            self.db_connection.commit()

            # Record individual items in order_details table
            for item_id, quantity in order_items:
                cursor.execute("""
                    INSERT INTO order_details (order_id, item_id, quantity)
                    VALUES (%s, %s, %s);
                """, (order_id, item_id, quantity))
                self.db_connection.commit()

            return f"\nOrder confirmed. Order ID: {order_id}. Total amount: ₹{total_amount:.2f}"

        except mysql.connector.Error as e:
            self.db_connection.rollback()  # Rollback the transaction on error
            print(f"Error processing order: {e}")
            return "Error processing order. Please try again."

    def cancel_order(self, order_id, cancel_reason):
        try:
            cursor = self.db_connection.cursor()

            # Check if order exists and is pending
            cursor.execute("SELECT order_status FROM orders WHERE order_id = %s;", (order_id,))
            order_status = cursor.fetchone()

            if not order_status:
                return "Order not found."
            elif order_status[0] != 'Pending':
                return "Cannot cancel order. It is already completed or cancelled."
            else:
                # Update order status to cancelled
                cursor.execute("UPDATE orders SET order_status = 'Cancelled' WHERE order_id = %s;", (order_id,))
                self.db_connection.commit()

                # Fetch transaction amount for refund history
                cursor.execute("SELECT total_amount FROM orders WHERE order_id = %s;", (order_id,))
                total_amount = cursor.fetchone()[0]

                # Record cancellation in cancelled_orders table
                cursor.execute("""
                    INSERT INTO cancelled_orders (order_id, cancel_reason)
                    VALUES (%s, %s);
                """, (order_id, cancel_reason))
                self.db_connection.commit()

                # Record refund in refund history
                cursor.execute("""
                    INSERT INTO refund_history (order_id, refund_amount, refund_reason)
                    VALUES (%s, %s, %s);
                """, (order_id, total_amount, cancel_reason))
                self.db_connection.commit()

                return f"Order {order_id} cancelled successfully. Refund processed."

        except mysql.connector.Error as e:
            self.db_connection.rollback()  # Rollback the transaction on error
            print(f"Error cancelling order: {e}")
            return "Error cancelling order. Please try again."

    def view_transaction_history(self):
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT th.transaction_id, th.order_id, th.transaction_amount, th.transaction_date,
                       GROUP_CONCAT(CONCAT(m.item_name, ' (₹', m.price, ')') SEPARATOR ', ') AS items
                FROM transaction_history th
                INNER JOIN orders o ON th.order_id = o.order_id
                INNER JOIN order_details od ON o.order_id = od.order_id
                INNER JOIN menu m ON od.item_id = m.item_id
                GROUP BY th.transaction_id
                ORDER BY th.transaction_date DESC;
            """)
            transactions = cursor.fetchall()

            if not transactions:
                return "No transaction history found."
            
            print("\nTransaction History:")
            for transaction in transactions:
                print(f"Transaction ID: {transaction[0]}, Order ID: {transaction[1]}, "
                      f"Items: {transaction[4]}, Amount: ₹{transaction[2]:.2f}, Date: {transaction[3]}")

        except mysql.connector.Error as e:
            print(f"Error fetching transaction history: {e}")
            return "Error fetching transaction history. Please try again."

    def run(self):
        print("Welcome to Food Delivery Chatbot!")
        print("Ask me anything related to food delivery or type 'exit' to quit.")

        while True:
            print("\nOptions:")
            print("1. Show Menu")
            print("2. Create Order")
            print("3. Cancel Order")
            print("4. View Transaction History")
            print("5. Exit")

            user_input = input("\nYou: ")

            if user_input.lower() == 'exit' or user_input == '5':
                print("Exiting...")
                break
            elif user_input == '1':
                self.display_menu()
            elif user_input == '2':
                try:
                    customer_name = input("Enter your name: ")
                    delivery_address = input("Enter delivery address: ")
                    phone = input("Enter your phone number: ")

                    order_details = {}
                    print("\nMenu:")
                    for item in self.menu_items:
                        print(f"{item[1]} - ₹{item[4]:.2f}")

                    order_input = input("\nEnter item name and quantity (e.g., Butter Chicken X 2) separated by commas: ")
                    parts = order_input.split(',')
                    for part in parts:
                        part = part.strip()
                        if ' X ' in part:
                            item_name, quantity = part.split(' X ')
                            item_name = item_name.strip()
                            quantity = int(quantity.strip())
                            if item_name in order_details:
                                order_details[item_name] += quantity
                            else:
                                order_details[item_name] = quantity
                        else:
                            print(f"Invalid input format for item: {part}. Please use 'Item Name X Quantity' format.")
                            continue

                    response = self.create_order(customer_name, delivery_address, phone, order_details)
                    print("Bot:", response)

                except ValueError:
                    print("Invalid input. Please try again.")
            elif user_input == '3':
                try:
                    order_id = int(input("Enter order ID to cancel: "))
                    cancel_reason = input("Enter cancellation reason: ")
                    response = self.cancel_order(order_id, cancel_reason)
                    print("Bot:", response)

                except ValueError:
                    print("Invalid input. Please enter a valid order ID.")
            elif user_input == '4':
                self.view_transaction_history()
            else:
                print("Invalid choice. Please choose a valid option.")

        self.db_connection.close()
        print("MySQL connection closed.")

if __name__ == "__main__":
    chatbot = FoodDeliveryChatbot()
    chatbot.run()
