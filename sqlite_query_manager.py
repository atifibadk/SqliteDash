import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLineEdit, QListWidget, QTextEdit, 
                             QDialog, QLabel, QFormLayout, QMessageBox, QFileDialog, 
                             QSplitter, QTableView, QHeaderView, QListWidgetItem,
                             QComboBox, QInputDialog)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QAbstractTableModel
import sqlite3
import json
import pandas as pd
import re

class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._data.columns[col]
        return None

class QuestionDialog(QDialog):
    def __init__(self, parent=None, conn=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Add New Question")
        self.setModal(True)
        self.initUI()
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QLineEdit, QTextEdit {
                background-color: white;
                color: black;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 6px;
            }
            QLabel {
                color: black;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

    def initUI(self):
        layout = QFormLayout()

        self.question_input = QLineEdit()
        layout.addRow("Question:", self.question_input)

        self.description_input = QTextEdit()
        layout.addRow("Description:", self.description_input)

        self.sql_input = QTextEdit()
        layout.addRow("SQL (use {input_name} for dynamic inputs):", self.sql_input)

        self.dynamic_inputs = QTextEdit()
        layout.addRow("Dynamic Inputs (format: input_name|column_name, one per line):", self.dynamic_inputs)

        self.submit_button = QPushButton("Add Question")
        self.submit_button.clicked.connect(self.validate_and_accept)
        layout.addRow(self.submit_button)

        self.setLayout(layout)

    def validate_and_accept(self):
        if not self.question_input.text() or not self.sql_input.toPlainText():
            QMessageBox.warning(self, "Error", "Question and SQL are required.")
            return

        if not self.sql_input.toPlainText().lower().startswith("select"):
            QMessageBox.warning(self, "Error", "Only SELECT queries are allowed.")
            return

        # Validate dynamic inputs
        inputs = self.parse_dynamic_inputs()
        sql = self.sql_input.toPlainText()
        for input_name in inputs.keys():
            if f"{{{input_name}}}" not in sql:
                QMessageBox.warning(self, "Error", f"Input {input_name} is not used in the SQL query.")
                return

        self.accept()

    def parse_dynamic_inputs(self):
        inputs = {}
        for line in self.dynamic_inputs.toPlainText().split('\n'):
            if '|' in line:
                input_name, column_name = line.split('|')
                inputs[input_name.strip()] = column_name.strip()
        return inputs

class SQLiteQuestionManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQLite Question Manager")
        self.setGeometry(100, 100, 1400, 900)
        
        self.db_path = ""
        self.conn = None
        self.questions = {}
        self.current_results = {}
        
        self.init_ui()
        self.set_style()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        
        # Left panel
        left_panel = QVBoxLayout()
        
        # Database selection layout
        db_layout = QHBoxLayout()
        self.db_path_input = QLineEdit()
        self.db_path_input.setPlaceholderText("Enter SQLite database path")
        self.db_path_input.setReadOnly(True)
        db_layout.addWidget(self.db_path_input)
        
        self.browse_db_button = QPushButton("Browse")
        self.browse_db_button.clicked.connect(self.browse_database)
        db_layout.addWidget(self.browse_db_button)
        
        left_panel.addLayout(db_layout)
        
        self.load_db_button = QPushButton("Load Database")
        self.load_db_button.clicked.connect(self.load_database)
        left_panel.addWidget(self.load_db_button)
        
        self.unload_db_button = QPushButton("Unload Database")
        self.unload_db_button.clicked.connect(self.unload_database)
        self.unload_db_button.setEnabled(False)
        left_panel.addWidget(self.unload_db_button)
        
        self.create_question_button = QPushButton("Create Question")
        self.create_question_button.clicked.connect(self.create_question)
        left_panel.addWidget(self.create_question_button)
        
        self.saved_questions_list = QListWidget()
        self.saved_questions_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.saved_questions_list.itemDoubleClicked.connect(self.show_question_details)
        left_panel.addWidget(self.saved_questions_list)
        
        self.run_questions_button = QPushButton("Run Selected Questions")
        self.run_questions_button.clicked.connect(self.run_selected_questions)
        left_panel.addWidget(self.run_questions_button)
        
        self.save_questionnaire_button = QPushButton("Save Questionnaire")
        self.save_questionnaire_button.clicked.connect(self.save_questionnaire)
        left_panel.addWidget(self.save_questionnaire_button)
        
        self.load_questionnaire_button = QPushButton("Load Questionnaire")
        self.load_questionnaire_button.clicked.connect(self.load_questionnaire)
        left_panel.addWidget(self.load_questionnaire_button)
        

        
        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(10, 10, 10, 10)  # Add some padding
        
        # Result selection dropdown
        self.result_selector = QComboBox()
        self.result_selector.currentIndexChanged.connect(self.display_selected_result)
        self.result_selector.setStyleSheet("background-color: white;")
        right_panel.addWidget(self.result_selector)
        
        # Question and description display
        self.question_display = QLabel()
        self.question_display.setStyleSheet("background-color: white; padding: 5px;")
        self.question_display.setWordWrap(True)
        self.description_display = QLabel()
        self.description_display.setStyleSheet("background-color: white; padding: 5px;")
        self.description_display.setWordWrap(True)
        right_panel.addWidget(self.question_display)
        right_panel.addWidget(self.description_display)
        
        # Results table
        self.results_table = QTableView()
        self.results_table.setStyleSheet("background-color: white;")
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_panel.addWidget(self.results_table)
        
        
        # Main layout
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        #left_widget.setStyleSheet("background-color: #f0f0f0;")
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        #right_widget.setStyleSheet("background-color: #f0f0f0;")  # Light gray background
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Set the initial sizes of the splitter
        splitter.setSizes([400, 1000])  # Adjust these values as needed
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        
        save_action = file_menu.addAction('Save State')
        save_action.triggered.connect(self.save_application_state)
        
        load_action = file_menu.addAction('Load State')
        load_action.triggered.connect(self.load_application_state)

        self.update_ui_state()
    
    def set_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit, QTextEdit, QListWidget, QTableView, QComboBox {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
                color: black;  /* Explicitly set text color to black */
            }
            QLabel {
                background-color: transparent;
                color: black;  /* Ensure label text is black */
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                color: black;
                padding: 5px;
                border: 1px solid #dcdcdc;
            }
        """)
        
        font = QFont("Arial", 10)
        QApplication.instance().setFont(font)




    def browse_database(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select SQLite Database", "", "SQLite Database (*.db *.sqlite);;All Files (*)")
        if file_path:
            self.db_path_input.setText(file_path)
    
    def load_database(self):
        self.db_path = self.db_path_input.text()
        if not os.path.exists(self.db_path):
            QMessageBox.warning(self, "Error", "Database file not found.")
            return
        
        try:
            self.conn = sqlite3.connect(self.db_path)
            QMessageBox.information(self, "Success", "Database loaded successfully.")
            self.update_ui_state()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Error", f"Failed to connect to database: {e}")
    
    def unload_database(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.db_path = ""
            self.db_path_input.clear()
            QMessageBox.information(self, "Success", "Database unloaded successfully.")
            self.update_ui_state()
    
    def update_ui_state(self):
        database_loaded = self.conn is not None
        self.db_path_input.setEnabled(not database_loaded)
        self.browse_db_button.setEnabled(not database_loaded)
        self.load_db_button.setEnabled(not database_loaded)
        self.unload_db_button.setEnabled(database_loaded)
        self.create_question_button.setEnabled(database_loaded)
        self.run_questions_button.setEnabled(database_loaded)
    
    def create_question(self):
        dialog = QuestionDialog(self, self.conn)
        if dialog.exec():
            question = dialog.question_input.text()
            description = dialog.description_input.toPlainText()
            sql = dialog.sql_input.toPlainText()
            dynamic_inputs = dialog.parse_dynamic_inputs()
            
            self.questions[question] = {
                "description": description,
                "sql": sql,
                "dynamic_inputs": dynamic_inputs
            }
            self.saved_questions_list.addItem(question)
    
    def save_questionnaire(self):
        if not self.questions:
            QMessageBox.warning(self, "Error", "No questions to save.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, "Save Questionnaire", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.questions, f, indent=2)
            QMessageBox.information(self, "Success", "Questionnaire saved successfully.")
    
    def load_questionnaire(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Questionnaire", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                loaded_questions = json.load(f)
            
            self.questions = loaded_questions
            self.saved_questions_list.clear()
            self.saved_questions_list.addItems(self.questions.keys())
            
            QMessageBox.information(self, "Success", "Questionnaire loaded successfully.")
    
    def save_application_state(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Application State", "", "JSON Files (*.json)")
        if filename:
            state = {
                "db_path": self.db_path,
                "questions": self.questions
            }
            with open(filename, 'w') as f:
                json.dump(state, f)
            QMessageBox.information(self, "Success", "Application state saved successfully.")
    
    def load_application_state(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Application State", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                state = json.load(f)
            
            self.db_path = state["db_path"]
            self.db_path_input.setText(self.db_path)
            self.load_database()
            
            self.questions = state["questions"]
            self.saved_questions_list.clear()
            self.saved_questions_list.addItems(self.questions.keys())
            
            QMessageBox.information(self, "Success", "Application state loaded successfully.")

    def show_question_details(self, item):
        question = item.text()
        details = self.questions[question]
        message = f"Question: {question}\n\nDescription: {details['description']}\n\nSQL: {details['sql']}"
        QMessageBox.information(self, "Question Details", message)


    def create_question(self):
        dialog = QuestionDialog(self, self.conn)
        if dialog.exec():
            question = dialog.question_input.text()
            description = dialog.description_input.toPlainText()
            sql = dialog.sql_input.toPlainText()
            dynamic_inputs = dialog.parse_dynamic_inputs()
            
            self.questions[question] = {
                "description": description,
                "sql": sql,
                "dynamic_inputs": dynamic_inputs
            }
            self.saved_questions_list.addItem(question)

    def run_selected_questions(self):
        if not self.conn:
            QMessageBox.warning(self, "Error", "Please load a database first.")
            return
        
        selected_items = self.saved_questions_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "Please select at least one question to run.")
            return
        
        self.current_results.clear()
        self.result_selector.clear()
        
        for item in selected_items:
            question = item.text()
            details = self.questions[question]
            sql = details['sql']
            dynamic_inputs = details.get('dynamic_inputs', {}) 
            
            # Collect user inputs
            user_inputs = {}
            for input_name, column_name in dynamic_inputs.items():
                if self.conn:
                    try:
                        df = pd.read_sql_query(f"SELECT DISTINCT {column_name} FROM ({sql})", self.conn)
                        values = df[column_name].tolist()
                        value, ok = QInputDialog.getItem(self, f"Input for {input_name}", 
                                                         f"Select value for {input_name}:", 
                                                         [str(v) for v in values], 0, False)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to fetch values for {input_name}: {str(e)}")
                        value, ok = QInputDialog.getText(self, f"Input for {input_name}", 
                                                         f"Enter value for {input_name}:")
                else:
                    value, ok = QInputDialog.getText(self, f"Input for {input_name}", 
                                                     f"Enter value for {input_name}:")
                if ok:
                    user_inputs[input_name] = value
                else:
                    return  # User cancelled input
            
            # Replace placeholders in SQL
            for input_name, value in user_inputs.items():
                sql = sql.replace(f"{{{input_name}}}", f"'{value}'")
            
            try:
                df = pd.read_sql_query(sql, self.conn)
                self.current_results[question] = {
                    'dataframe': df,
                    'description': details['description']
                }
                self.result_selector.addItem(question)
            except Exception as e:
                error_message = f"Error executing query for question '{question}':\n{str(e)}"
                QMessageBox.warning(self, "Error", error_message)
                self.current_results[question] = {
                    'dataframe': pd.DataFrame({'Error': [error_message]}),
                    'description': details['description']
                }
                self.result_selector.addItem(f"{question} (Error)")
        
        if self.current_results:
            self.result_selector.setCurrentIndex(0)
            self.display_selected_result(0)
    
    def display_selected_result(self, index):
        if index < 0:
            return
        
        question = self.result_selector.currentText()
        result = self.current_results[question]
        
        self.question_display.setText(f"<b>Question:</b> {question}")
        self.description_display.setText(f"<b>Description:</b> {result['description']}")
        
        model = PandasModel(result['dataframe'])
        self.results_table.setModel(model)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SQLiteQuestionManager()
    window.show()
    sys.exit(app.exec())