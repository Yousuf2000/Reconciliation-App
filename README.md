🧾 Reconciliation App

A Flask web application that performs credit-debit reconciliation from uploaded financial data (CSV/XLS/XLSX). The app allows users to upload a dataset, automatically matches credit and debit transactions, and provides an interactive interface to filter, view, and download reconciliation results.

🚀 Features

✅ Upload & Process Files

Supports .csv, .xls, and .xlsx file formats.

Automatically separates credits and debits and performs matching based on transaction amounts.

✅ Smart Reconciliation

Tags each transaction as Donation (credit) or Charity (debit).

Matches debits against credits in chronological order.

Tracks used and remaining credit amounts for each transaction.

✅ Interactive Web Interface

Built with Flask and Bootstrap 5 for responsive UI.

Autocomplete filters for Credit Date, Credit UUID, and Credit Amount.

Displays filtered results dynamically without page reload.

✅ Downloadable Reports

Download filtered results or complete reconciliation as Excel files.

✅ Session-Based Data Handling

Each user session stores its own processed dataset in memory.

📂 Folder Structure
ReconciliationApp/
│
├── app.py                # Main Flask application file
├── requirements.txt      # Required Python packages
└── README.md             # Documentation (this file)



📤 How to Use

Upload File

Choose a CSV/XLS/XLSX file containing columns like ID, UUID, Date, and Amount.

Click Upload & Process to perform reconciliation.

Filter Results

Use the autocomplete fields under Filters (Credit-side driven) to filter by date, UUID, or amount.

Click Show Results to view the filtered records in the table.

Download Files

Click Download Filtered to export only the visible filtered results.

Click Download Complete to export the entire reconciliation output.

Reset Filters

Click Reset Filters to clear all selections and start fresh.



🧮 Reconciliation Logic

The app processes the uploaded file as follows:

Converts the Amount column to numeric and Date column to standard datetime format.

Tags:

Positive amounts as Donation (Credit).

Negative amounts as Charity (Debit).

Matches debit transactions against available credits in chronological order.

Records details such as:

Credit & Debit IDs, UUIDs, Dates

Used amount, Remaining Credit, and Tags

The result is a detailed reconciliation DataFrame showing how each debit was fulfilled from credits.
