import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLineEdit, QTextEdit, 
                             QDialog, QLabel, QFormLayout, QMessageBox, QFileDialog, 
                             QSplitter, QTableView, QHeaderView, QTreeWidget, QTreeWidgetItem,
                             QComboBox, QCheckBox, QInputDialog)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QAbstractTableModel
import sqlite3
import json
import pandas as pd

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
        layout.addRow("SQL:", self.sql_input)

        self.dynamic_toggle = QCheckBox("Enable Dynamic Input")
        self.dynamic_toggle.stateChanged.connect(self.toggle_dynamic_input)
        layout.addRow(self.dynamic_toggle)

        self.dynamic_inputs = QTextEdit()
        self.dynamic_inputs.setVisible(False)
        layout.addRow("Dynamic Inputs (format: input_name|column_name, one per line):", self.dynamic_inputs)

        self.submit_button = QPushButton("Add Question")
        self.submit_button.clicked.connect(self.validate_and_accept)
        layout.addRow(self.submit_button)

        self.setLayout(layout)

    def toggle_dynamic_input(self, state):
        self.dynamic_inputs.setVisible(state == Qt.CheckState.Checked)

    def validate_and_accept(self):
        if not self.question_input.text() or not self.sql_input.toPlainText():
            QMessageBox.warning(self, "Error", "Question and SQL are required.")
            return

        if not self.sql_input.toPlainText().lower().startswith("select"):
            QMessageBox.warning(self, "Error", "Only SELECT queries are allowed.")
            return

        # Validate dynamic inputs
        if self.dynamic_toggle.isChecked():
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
        self.question_groups = {}
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
        
        self.question_tree = QTreeWidget()
        self.question_tree.setHeaderLabels(["Questions"])
        self.question_tree.itemDoubleClicked.connect(self.show_question_details)
        left_panel.addWidget(self.question_tree)
        
        self.run_questions_button = QPushButton("Run Selected Questions")
        self.run_questions_button.clicked.connect(self.run_selected_questions)
        left_panel.addWidget(self.run_questions_button)
        
        self.save_questionnaire_button = QPushButton("Save Questionnaire")
        self.save_questionnaire_button.clicked.connect(self.save_questionnaire)
        left_panel.addWidget(self.save_questionnaire_button)
        
        self.load_questionnaire_button = QPushButton("Load Questionnaire")
        self.load_questionnaire_button.clicked.connect(self.load_questionnaire)
        left_panel.addWidget(self.load_questionnaire_button)
        
        self.load_single_question_button = QPushButton("Load Single Question")
        self.load_single_question_button.clicked.connect(self.load_single_question)
        left_panel.addWidget(self.load_single_question_button)
        
        # Right panel
        right_panel = QVBoxLayout()
        
        # Result selection dropdown
        self.result_selector = QComboBox()
        self.result_selector.currentIndexChanged.connect(self.display_selected_result)
        right_panel.addWidget(self.result_selector)
        
        # Question and description display
        self.question_display = QLabel()
        self.question_display.setWordWrap(True)
        right_panel.addWidget(self.question_display)
        
        self.description_display = QLabel()
        self.description_display.setWordWrap(True)
        right_panel.addWidget(self.description_display)
        
        # Results table
        self.results_table = QTableView()
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_panel.addWidget(self.results_table)
        
        # Main layout
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        
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
            QLineEdit, QTextEdit, QListWidget, QTableView, QComboBox, QTreeWidget {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
                color: black;
            }
            QLabel {
                color: black;
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
            dynamic_inputs = dialog.parse_dynamic_inputs() if dialog.dynamic_toggle.isChecked() else {}
            
            group, ok = QInputDialog.getText(self, "Question Group", "Enter group name for this question:")
            if ok:
                if group not in self.question_groups:
                    self.question_groups[group] = []
                self.question_groups[group].append(question)
                
                self.questions[question] = {
                    "description": description,
                    "sql": sql,
                    "dynamic_inputs": dynamic_inputs
                }
                self.update_question_tree()
    
    def update_question_tree(self):
        self.question_tree.clear()
        for group, questions in self.question_groups.items():
            group_item = QTreeWidgetItem(self.question_tree, [group])
            for question in questions:
                QTreeWidgetItem(group_item, [question])
        self.question_tree.expandAll()
    
    def show_question_details(self, item, column):
        if item.parent():  # It's a question, not a group
            question = item.text(0)
            details = self.questions[question]
            message = f"Question: {question}\n\nDescription: {details['description']}\n\nSQL: {details['sql']}"
            if details.get('dynamic_inputs'):
                message += f"\n\nDynamic Inputs: {details['dynamic_inputs']}"
            QMessageBox.information(self, "Question Details", message)
    
    def run_selected_questions(self):
        if not self.conn:
            QMessageBox.warning(self, "Error", "Please load a database first.")
            return
        
        selected_items = self.question_tree.selectedItems()
        questions_to_run = []
        for item in selected_items:
            if item.parent():  # It's a question, not a group
                questions_to_run.append(item.text(0))
            else:  # It's a group, add all child questions
                for i in range(item.childCount()):
                    questions_to_run.append(item.child(i).text(0))
        
        if not questions_to_run:
            QMessageBox.warning(self, "Error", "Please select at least one question to run.")
            return
        
        self.current_results.clear()
        self.result_selector.clear()
        
        for question in questions_to_run:
            details = self.questions[question]
            sql = details['sql']
            dynamic_inputs = details.get('dynamic_inputs', {})
            
            if dynamic_inputs:
                reply = QMessageBox.question(self, 'Re-run Dynamic Question', 
                                             'Do you want to create a new question or replace the existing one?',
                                             QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
                
                if reply == QMessageBox.StandardButton.Save:
                    new_question = f"{question} (New)"
                    self.questions[new_question] = details.copy()
                    question = new_question
                    # Add the new question to the appropriate group
                    for group, questions in self.question_groups.items():
                        if question in questions:
                            self.question_groups[group].append(new_question)
                            break
                elif reply == QMessageBox.StandardButton.Cancel:
                    continue
            
            # Collect user inputs for dynamic questions
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
                    break  # User cancelled input
            
            if len(user_inputs) != len(dynamic_inputs):
                continue  # Skip this question if user cancelled any input
            
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
        
        self.update_question_tree()
    
    def display_selected_result(self, index):
        if index < 0:
            return
        
        question = self.result_selector.currentText()
        result = self.current_results[question]
        
        self.question_display.setText(f"<b>Question:</b> {question}")
        self.description_display.setText(f"<b>Description:</b> {result['description']}")
        
        model = PandasModel(result['dataframe'])
        self.results_table.setModel(model)
    
    def save_questionnaire(self):
        if not self.questions:
            QMessageBox.warning(self, "Error", "No questions to save.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, "Save Questionnaire", "", "JSON Files (*.json)")
        if filename:
            data = {
                "questions": self.questions,
                "groups": self.question_groups
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Success", "Questionnaire saved successfully.")
    
    def load_questionnaire(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Questionnaire", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.questions = data.get("questions", {})
            self.question_groups = data.get("groups", {})
            self.update_question_tree()
            
            QMessageBox.information(self, "Success", "Questionnaire loaded successfully.")
    
    def load_single_question(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Single Question", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                question_data = json.load(f)
            
            if isinstance(question_data, dict) and len(question_data) == 1:
                question = next(iter(question_data))
                self.questions[question] = question_data[question]
                
                group, ok = QInputDialog.getText(self, "Question Group", "Enter group name for this question:")
                if ok:
                    if group not in self.question_groups:
                        self.question_groups[group] = []
                    self.question_groups[group].append(question)
                
                self.update_question_tree()
                QMessageBox.information(self, "Success", f"Question '{question}' loaded successfully.")
            else:
                QMessageBox.warning(self, "Error", "Invalid question file format.")
    
    def save_application_state(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Application State", "", "JSON Files (*.json)")
        if filename:
            state = {
                "db_path": self.db_path,
                "questions": self.questions,
                "groups": self.question_groups
            }
            with open(filename, 'w') as f:
                json.dump(state, f, indent=2)
            QMessageBox.information(self, "Success", "Application state saved successfully.")
    
    def load_application_state(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Application State", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                state = json.load(f)
            
            self.db_path = state.get("db_path", "")
            self.db_path_input.setText(self.db_path)
            self.load_database()
            
            self.questions = state.get("questions", {})
            self.question_groups = state.get("groups", {})
            self.update_question_tree()
            
            QMessageBox.information(self, "Success", "Application state loaded successfully.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SQLiteQuestionManager()
    window.show()
    sys.exit(app.exec())