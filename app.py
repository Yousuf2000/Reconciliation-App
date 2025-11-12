from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for, jsonify, session
import pandas as pd
import io
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "Yousuf@123"
# Store processed data in memory per user session
processed_data = {}  # key: session_id, value: DataFrame

ALLOWED_EXTENSIONS = {"csv", "xls", "xlsx"}


# ---------- HTML template ----------
PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reconciliation App</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { margin: 20px; }
  .filters { padding: 20px; background: #f8f9fa; border-radius: 8px; margin-top: 20px; }
  .filters label { font-weight: 500; }
  .table-container { margin-top: 20px; max-height: 500px; overflow-y: auto; }
  .autocomplete-items {
      position: absolute;
      border: 1px solid #d4d4d4;
      border-bottom: none;
      border-top: none;
      z-index: 99;
      background-color: white;
      max-height: 200px;
      overflow-y: auto;
  }
  .autocomplete-items div {
      padding: 10px;
      cursor: pointer;
  }
  .autocomplete-items div:hover { background-color: #e9e9e9; }
</style>
</head>
<body>
<div class="container">
<h2 class="mb-4">Reconciliation App</h2>

<form method="post" enctype="multipart/form-data" class="mb-3">
  <div class="input-group">
    <input type="file" class="form-control" name="file" required>
    <button class="btn btn-primary" type="submit">Upload & Process</button>
  </div>
</form>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <div class="mb-3">
      {% for m in messages %}
        <div class="alert alert-danger">{{ m }}</div>
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}

<div id="controls" style="display: {{ 'block' if processed else 'none' }};">
  <div class="filters">
    <h5>Filters (Credit-side driven)</h5>
    <div class="row g-3 align-items-end">
      <div class="col-md-3 position-relative">
        <label for="credit_date" class="form-label">Credit Date</label>
        <input class="form-control" id="credit_date">
      </div>
      <div class="col-md-3 position-relative">
        <label for="credit_uuid" class="form-label">Credit UUID</label>
        <input class="form-control" id="credit_uuid">
      </div>
      <div class="col-md-3 position-relative">
        <label for="credit_amount" class="form-label">Credit Amount</label>
        <input class="form-control" id="credit_amount">
      </div>
      <div class="col-md-3 d-grid gap-2">
        <button class="btn btn-success" id="showBtn">Show Results</button>
        <button class="btn btn-info" id="downloadFilteredBtn">Download Filtered</button>
        <button class="btn btn-secondary" id="downloadCompleteBtn">Download Complete</button>
        <button class="btn btn-outline-dark" id="resetBtn">Reset Filters</button>
      </div>
    </div>
  </div>

  <div class="table-container">
    <div id="tableArea"></div>
  </div>
</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
let fullOptions = { credit_date: [], credit_uuid: [], credit_amount: [] };

// ---------- Autocomplete function ----------
function autocomplete(input, arr) {
    let currentFocus;
    input.addEventListener("input", function() {
        const val = this.value;
        closeAllLists();
        if (!val) return false;
        currentFocus = -1;
        const list = document.createElement("DIV");
        list.setAttribute("class", "autocomplete-items");
        this.parentNode.appendChild(list);
        arr.forEach(item => {
            if (item.toString().toLowerCase().includes(val.toLowerCase())) {
                const itemDiv = document.createElement("DIV");
                itemDiv.innerHTML = item;
                itemDiv.addEventListener("click", function(){
                    input.value = item;
                    closeAllLists();
                    input.dispatchEvent(new Event('input')); // trigger dependent filters
                });
                list.appendChild(itemDiv);
            }
        });
    });

    input.addEventListener("keydown", function(e) {
        let x = this.parentNode.querySelector(".autocomplete-items");
        if (x) x = x.getElementsByTagName("div");
        if (!x) return;
        if (e.keyCode == 40) { currentFocus++; addActive(x); }
        else if (e.keyCode == 38) { currentFocus--; addActive(x); }
        else if (e.keyCode == 13) { e.preventDefault(); if (currentFocus > -1) x[currentFocus].click(); }
    });

    function addActive(x) { if (!x) return false; removeActive(x); if (currentFocus >= x.length) currentFocus = 0; if (currentFocus < 0) currentFocus = x.length-1; x[currentFocus].classList.add("autocomplete-active"); }
    function removeActive(x) { for (let i=0;i<x.length;i++) x[i].classList.remove("autocomplete-active"); }
    function closeAllLists(elmnt) { const items = document.getElementsByClassName("autocomplete-items"); for (let i=0;i<items.length;i++) { if (elmnt != items[i] && elmnt != input) items[i].parentNode.removeChild(items[i]); } }
    document.addEventListener("click", function (e) { closeAllLists(e.target); });
}

// ---------- Fetch filter options ----------
async function fetchOptions(currentFilters={}) {
    const resp = await fetch('/filter_options', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(currentFilters)
    });
    const data = await resp.json();
    fullOptions.credit_date = data.dates;
    fullOptions.credit_uuid = data.uuids;
    fullOptions.credit_amount = data.amounts;
}

// ---------- Update dependent filters ----------
async function onDropdownChange() {
    const filters = {
        credit_date: document.getElementById('credit_date').value,
        credit_uuid: document.getElementById('credit_uuid').value,
        credit_amount: document.getElementById('credit_amount').value
    };
    await fetchOptions(filters);
}

// ---------- Render table ----------
function renderTable(rows) {
    const area = document.getElementById('tableArea');
    if (!rows || rows.length === 0) {
        area.innerHTML = '<p class="mt-3">No rows to display.</p>';
        return;
    }
    let html = '<table class="table table-striped table-bordered table-hover"><thead class="table-dark"><tr>';
    Object.keys(rows[0]).forEach(h => html += '<th>' + h + '</th>');
    html += '</tr></thead><tbody>';
    rows.forEach(r => {
        html += '<tr>';
        Object.values(r).forEach(v => html += '<td>' + (v === null ? '' : String(v)) + '</td>');
        html += '</tr>';
    });
    html += '</tbody></table>';
    area.innerHTML = html;
}

// ---------- Event listeners ----------
document.addEventListener('DOMContentLoaded', function(){
  {% if processed %}
    // fetch initial options
    fetchOptions().then(()=>{
        // initialize autocomplete once
        autocomplete(document.getElementById('credit_date'), fullOptions.credit_date);
        autocomplete(document.getElementById('credit_uuid'), fullOptions.credit_uuid);
        autocomplete(document.getElementById('credit_amount'), fullOptions.credit_amount);
    });
  {% endif %}

  ['credit_date','credit_uuid','credit_amount'].forEach(id => {
      document.getElementById(id).addEventListener('input', onDropdownChange);
  });

  document.getElementById('showBtn').addEventListener('click', async function(e){
    e.preventDefault();
    const filters = {
      credit_date: document.getElementById('credit_date').value,
      credit_uuid: document.getElementById('credit_uuid').value,
      credit_amount: document.getElementById('credit_amount').value
    };
    const resp = await fetch('/show_results', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(filters)
    });
    const data = await resp.json();
    renderTable(data.rows);
  });

  document.getElementById('downloadFilteredBtn').addEventListener('click', function(e){
    e.preventDefault();
    const params = new URLSearchParams({
      credit_date: document.getElementById('credit_date').value || '',
      credit_uuid: document.getElementById('credit_uuid').value || '',
      credit_amount: document.getElementById('credit_amount').value || ''
    });
    window.location = '/download_filtered?' + params.toString();
  });

  document.getElementById('downloadCompleteBtn').addEventListener('click', function(e){
    e.preventDefault();
    window.location = '/download_complete';
  });

  document.getElementById('resetBtn').addEventListener('click', async function(e){
    e.preventDefault();
    document.getElementById('credit_date').value = '';
    document.getElementById('credit_uuid').value = '';
    document.getElementById('credit_amount').value = '';
    await fetchOptions({});
    renderTable([]);
  });
});
</script>
</body>
</html>

"""

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def run_reconciliation(df):
    df = df.copy()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    df["Tags"] = df["Amount"].apply(lambda x: "Donation" if x > 0 else "Charity")
    credits_df = df[df["Amount"] > 0].copy().sort_values("Date").reset_index(drop=True)
    debits_df = df[df["Amount"] < 0].copy().sort_values("Date").reset_index(drop=True)
    remaining_credits = {row.ID: row.Amount for row in credits_df.itertuples()}
    records = []
    for debit in debits_df.itertuples():
        debit_remaining = abs(debit.Amount)
        for credit in credits_df.itertuples():
            credit_remain = remaining_credits.get(credit.ID, 0)
            if credit_remain <= 0:
                continue
            used = min(debit_remaining, credit_remain)
            remaining_credits[credit.ID] = credit_remain - used
            debit_remaining -= used
            records.append({
                "Credit_Date": credit.Date,
                "Credit_ID": credit.ID,
                "Credit_UUID": credit.UUID,
                "Credit_Tag": "Donation",
                "Credit_Amount": credit.Amount,
                "Used_From_Credit": used,
                "Credit_Remaining": remaining_credits[credit.ID],
                "Debit_Date": debit.Date,
                "Debit_ID": debit.ID,
                "Debit_UUID": debit.UUID,
                "Debit_Tag": "Charity",
                "Debit_Amount": abs(debit.Amount),
            })
            if debit_remaining == 0:
                break
    return pd.DataFrame(records)

@app.route("/", methods=["GET", "POST"])
def index():
    processed = False
    # Assign a unique session ID for the user if not exists
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    session_id = session["session_id"]

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("No file selected")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Allowed file types: csv, xls, xlsx")
            return redirect(request.url)
        ext = file.filename.rsplit(".", 1)[1].lower()
        try:
            df = pd.read_csv(file) if ext=="csv" else pd.read_excel(file)
            out_df = run_reconciliation(df)
            # store DataFrame in memory per session
            processed_data[session_id] = out_df
            processed = True
            flash("File processed successfully!")
        except Exception as e:
            flash(str(e))
    return render_template_string(PAGE, processed=processed)

@app.route("/filter_options", methods=["POST"])
def filter_options():
    session_id = session.get("session_id")
    if session_id not in processed_data:
        return jsonify({"dates": [], "uuids": [], "amounts": []})
    
    df = processed_data[session_id]
    current = request.get_json() or {}
    credit_df = df[df["Credit_Amount"] > 0].copy()
    if cd := current.get("credit_date"): credit_df = credit_df[credit_df["Credit_Date"]==cd]
    if cu := current.get("credit_uuid"): credit_df = credit_df[credit_df["Credit_UUID"]==cu]
    if ca := current.get("credit_amount"):
        try: ca_val = float(ca); credit_df = credit_df[credit_df["Credit_Amount"]==ca_val]
        except: credit_df = credit_df[credit_df["Credit_Amount"].astype(str)==ca]

    dates = sorted(credit_df["Credit_Date"].dropna().unique())
    uuids = sorted(credit_df["Credit_UUID"].dropna().unique())
    amounts = sorted([str(x) for x in credit_df["Credit_Amount"].dropna().unique()])
    return jsonify({"dates": dates, "uuids": uuids, "amounts": amounts})

@app.route("/show_results", methods=["POST"])
def show_results():
    session_id = session.get("session_id")
    if session_id not in processed_data:
        return jsonify({"rows":[]})
    df = processed_data[session_id]
    current = request.get_json() or {}
    cd, cu, ca = current.get("credit_date"), current.get("credit_uuid"), current.get("credit_amount")
    df_filtered = df.copy()
    if cd: df_filtered = df_filtered[df_filtered["Credit_Date"]==cd]
    if cu: df_filtered = df_filtered[df_filtered["Credit_UUID"]==cu]
    if ca:
        try: ca_val = float(ca); df_filtered = df_filtered[df_filtered["Credit_Amount"]==ca_val]
        except: df_filtered = df_filtered[df_filtered["Credit_Amount"].astype(str)==ca]
    rows = df_filtered.to_dict(orient="records")
    rows = [{k: (None if pd.isna(v) else v) for k,v in r.items()} for r in rows]
    return jsonify({"rows": rows})

@app.route("/download_filtered")
def download_filtered():
    session_id = session.get("session_id")
    if session_id not in processed_data:
        flash("No processed data available.")
        return redirect(url_for("index"))
    df = processed_data[session_id]
    cd, cu, ca = request.args.get("credit_date"), request.args.get("credit_uuid"), request.args.get("credit_amount")
    df_filtered = df.copy()
    if cd: df_filtered = df_filtered[df_filtered["Credit_Date"]==cd]
    if cu: df_filtered = df_filtered[df_filtered["Credit_UUID"]==cu]
    if ca:
        try: ca_val = float(ca); df_filtered = df_filtered[df_filtered["Credit_Amount"]==ca_val]
        except: df_filtered = df_filtered[df_filtered["Credit_Amount"].astype(str)==ca]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_filtered.to_excel(writer, index=False, sheet_name="Filtered_Reconciliation")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="reconciliation_filtered.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/download_complete")
def download_complete():
    session_id = session.get("session_id")
    if session_id not in processed_data:
        flash("No processed data available.")
        return redirect(url_for("index"))
    df = processed_data[session_id]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Complete_Reconciliation")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="reconciliation_complete.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__=="__main__":
    app.run(debug=True)



