import { useMemo, useState } from "react";
import { ArrowDownLeft, Check, FileText, Plus, Receipt, Send, Wallet, X } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);
const plusDays = days => { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); };
const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0));
const blankLine = () => ({ description: "", quantity: "1", unit_price: "", tax_amount: "0.00" });

export default function ReceivablesWorkspace({ customers = [], invoices = [], receipts = [], api, claims = {}, onChanged, onAddCustomer }) {
  const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
  const canInvoice = permissions.includes("ar:invoice:write");
  const canIssue = permissions.includes("ar:invoice:issue");
  const canReceipt = permissions.includes("ar:receipt:write");
  const [mode, setMode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState("");
  const [issueReason, setIssueReason] = useState({});
  const [invoiceForm, setInvoiceForm] = useState({ customer_id: "", invoice_number: "", currency: "INR", issue_date: today(), due_date: plusDays(30), notes: "", lines: [blankLine()] });
  const [receiptForm, setReceiptForm] = useState({ customer_id: "", currency: "INR", amount: "", received_date: today(), reference: "", method: "", allocations: [] });

  const filteredInvoices = useMemo(() => invoices.filter(row =>
    [row.invoice_number, row.customer_id, row.status, row.notes].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase())
  ), [invoices, query]);
  const activeCustomers = customers.filter(row => row.status === "Active");
  const invoiceTotal = invoiceForm.lines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0) + Number(line.tax_amount || 0), 0);
  const outstanding = invoices.reduce((sum, row) => sum + Number(row.outstanding || 0), 0);

  const changeInvoice = (key, value) => setInvoiceForm(current => ({ ...current, [key]: value }));
  const changeLine = (index, key, value) => setInvoiceForm(current => ({ ...current, lines: current.lines.map((line, i) => i === index ? { ...line, [key]: value } : line) }));
  const closeMode = () => { setMode(""); setError(""); };

  const createInvoice = async event => {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/v1/ar/invoices", { method: "POST", body: JSON.stringify({
        customer_id: invoiceForm.customer_id, invoice_number: invoiceForm.invoice_number || null,
        currency: invoiceForm.currency.toUpperCase(), issue_date: invoiceForm.issue_date, due_date: invoiceForm.due_date,
        notes: invoiceForm.notes || null, lines: invoiceForm.lines.map(line => ({
          description: line.description, quantity: line.quantity, unit_price: line.unit_price, tax_amount: line.tax_amount || "0.00"
        }))
      })});
      setMode(""); setNotice("Invoice saved as Draft. It must be issued as a separate authorized action."); await onChanged?.();
    } catch (err) { setError(err.message || "Invoice could not be created."); }
    finally { setBusy(false); }
  };

  const issue = async row => {
    const reason = issueReason[row.id] || "";
    if (reason.trim().length < 3) { setError("Enter a reason before issuing this invoice."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/api/v1/ar/invoices/${row.id}/issue`, { method: "POST", body: JSON.stringify({ expected_version: row.version, reason: reason.trim() }) });
      setNotice("Invoice issued successfully."); setIssueReason(current => ({ ...current, [row.id]: "" })); await onChanged?.();
    } catch (err) { setError(err.message || "Invoice could not be issued."); }
    finally { setBusy(false); }
  };

  const createReceipt = async event => {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const allocations = receiptForm.allocations.filter(item => item.invoice_id && Number(item.amount) > 0);
      await api("/api/v1/ar/receipts", { method: "POST", body: JSON.stringify({
        customer_id: receiptForm.customer_id, currency: receiptForm.currency.toUpperCase(),
        amount: receiptForm.amount, received_date: receiptForm.received_date,
        reference: receiptForm.reference || null, method: receiptForm.method || null, allocations
      })});
      setMode(""); setNotice("Receipt recorded. This records the received amount; it does not initiate or verify a bank transfer."); await onChanged?.();
    } catch (err) { setError(err.message || "Receipt could not be recorded."); }
    finally { setBusy(false); }
  };

  const eligibleInvoices = invoices.filter(row => row.customer_id === receiptForm.customer_id && ["Issued", "Partially Paid"].includes(row.status) && row.currency === receiptForm.currency.toUpperCase());
  const allocationTotal = receiptForm.allocations.reduce((sum, item) => sum + Number(item.amount || 0), 0);

  return <div className="receivables-workspace">
    <section className="metric-grid">
      <div className="metric-card"><div className="metric-top"><span>Customers</span><i><ArrowDownLeft size={17}/></i></div><strong>{customers.length}</strong><small>Customer master records</small></div>
      <div className="metric-card"><div className="metric-top"><span>Invoices</span><i><FileText size={17}/></i></div><strong>{invoices.length}</strong><small>Draft and issued invoices</small></div>
      <div className="metric-card"><div className="metric-top"><span>Outstanding</span><i><Wallet size={17}/></i></div><strong>{money(outstanding)}</strong><small>From current invoice balances</small></div>
      <div className="metric-card"><div className="metric-top"><span>Receipts</span><i><Receipt size={17}/></i></div><strong>{receipts.length}</strong><small>Recorded receipt entries</small></div>
    </section>
    <section className="panel list-panel">
      <div className="list-heading"><div><h2>Accounts receivable</h2><p>Customers, draft and issued invoices, receipt records and allocations.</p></div><div className="receivable-actions">
        {permissions.includes("ar:customer:write") && <button className="btn btn-quiet" onClick={onAddCustomer}><Plus size={14}/>Customer</button>}
        {canInvoice && <button className="btn btn-primary" onClick={() => { setMode("invoice"); setError(""); }}><Plus size={14}/>New invoice</button>}
        {canReceipt && <button className="btn btn-quiet" onClick={() => { setMode("receipt"); setError(""); }}><Plus size={14}/>Record receipt</button>}
      </div></div>
      {error && <div className="notice">{error}</div>}{notice && <div className="receivable-success"><Check size={15}/>{notice}</div>}
      {mode === "invoice" && <form className="receivable-form" onSubmit={createInvoice}>
        <div className="receivable-form-head"><div><h3>Create invoice draft</h3><p>Amounts and totals are calculated and validated by the API.</p></div><button type="button" className="icon-btn" onClick={closeMode}><X size={16}/></button></div>
        <div className="receivable-fields">
          <label>Customer<select required value={invoiceForm.customer_id} onChange={e => changeInvoice("customer_id", e.target.value)}><option value="">Select an active customer</option>{activeCustomers.map(row => <option key={row.id} value={row.id}>{row.legal_name}</option>)}</select></label>
          <label>Invoice number (optional)<input value={invoiceForm.invoice_number} onChange={e => changeInvoice("invoice_number", e.target.value)}/></label>
          <label>Currency<input required minLength="3" maxLength="3" value={invoiceForm.currency} onChange={e => changeInvoice("currency", e.target.value.toUpperCase())}/></label>
          <label>Issue date<input required type="date" value={invoiceForm.issue_date} onChange={e => changeInvoice("issue_date", e.target.value)}/></label>
          <label>Due date<input required type="date" min={invoiceForm.issue_date} value={invoiceForm.due_date} onChange={e => changeInvoice("due_date", e.target.value)}/></label>
          <label className="receivable-wide">Notes (optional)<textarea rows="2" value={invoiceForm.notes} onChange={e => changeInvoice("notes", e.target.value)}/></label>
        </div>
        <div className="receivable-lines-head"><h4>Invoice lines</h4><button type="button" className="btn btn-quiet" onClick={() => setInvoiceForm(current => ({ ...current, lines: [...current.lines, blankLine()] }))}><Plus size={14}/>Add line</button></div>
        {invoiceForm.lines.map((line, index) => <div className="receivable-line" key={index}>
          <label>Description<input required value={line.description} onChange={e => changeLine(index, "description", e.target.value)}/></label>
          <label>Quantity<input required type="number" min="0.0001" step="0.0001" value={line.quantity} onChange={e => changeLine(index, "quantity", e.target.value)}/></label>
          <label>Unit price<input required type="number" min="0" step="0.01" value={line.unit_price} onChange={e => changeLine(index, "unit_price", e.target.value)}/></label>
          <label>Tax amount<input type="number" min="0" step="0.01" value={line.tax_amount} onChange={e => changeLine(index, "tax_amount", e.target.value)}/></label>
          <button type="button" className="icon-btn" disabled={invoiceForm.lines.length === 1} onClick={() => setInvoiceForm(current => ({ ...current, lines: current.lines.filter((_, i) => i !== index) }))} aria-label="Remove invoice line"><X size={15}/></button>
        </div>)}
        <div className="receivable-total"><span>Estimated total</span><b>{money(invoiceTotal, invoiceForm.currency)}</b></div>
        <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={closeMode}>Cancel</button><button className="btn btn-primary" disabled={busy || !activeCustomers.length}>{busy ? "Saving…" : "Save draft"}</button></div>
        {!activeCustomers.length && <small className="field-help">Create an active customer before creating an invoice.</small>}
      </form>}
      {mode === "receipt" && <form className="receivable-form" onSubmit={createReceipt}>
        <div className="receivable-form-head"><div><h3>Record receipt</h3><p>Receipt recording does not initiate a payment or bank transfer.</p></div><button type="button" className="icon-btn" onClick={closeMode}><X size={16}/></button></div>
        <div className="receivable-fields">
          <label>Customer<select required value={receiptForm.customer_id} onChange={e => setReceiptForm(current => ({ ...current, customer_id: e.target.value, allocations: [] }))}><option value="">Select customer</option>{activeCustomers.map(row => <option key={row.id} value={row.id}>{row.legal_name}</option>)}</select></label>
          <label>Currency<input required minLength="3" maxLength="3" value={receiptForm.currency} onChange={e => setReceiptForm(current => ({ ...current, currency: e.target.value.toUpperCase(), allocations: [] }))}/></label>
          <label>Amount<input required type="number" min="0.01" step="0.01" value={receiptForm.amount} onChange={e => setReceiptForm(current => ({ ...current, amount: e.target.value }))}/></label>
          <label>Received date<input required type="date" value={receiptForm.received_date} onChange={e => setReceiptForm(current => ({ ...current, received_date: e.target.value }))}/></label>
          <label>Reference (optional)<input value={receiptForm.reference} onChange={e => setReceiptForm(current => ({ ...current, reference: e.target.value }))}/></label>
          <label>Method (optional)<input value={receiptForm.method} onChange={e => setReceiptForm(current => ({ ...current, method: e.target.value }))}/></label>
        </div>
        {eligibleInvoices.length > 0 && <div className="receivable-allocation"><h4>Allocate to invoices (optional)</h4>{eligibleInvoices.map(row => <label key={row.id}><span>{row.invoice_number || row.id.slice(0, 8)} · outstanding {money(row.outstanding, row.currency)}</span><input type="number" min="0" max={row.outstanding} step="0.01" placeholder="0.00" value={receiptForm.allocations.find(item => item.invoice_id === row.id)?.amount || ""} onChange={e => setReceiptForm(current => ({ ...current, allocations: [...current.allocations.filter(item => item.invoice_id !== row.id), { invoice_id: row.id, amount: e.target.value }] }))}/></label>)}<p>Allocated: {money(allocationTotal, receiptForm.currency)} · Receipt: {money(receiptForm.amount, receiptForm.currency)}</p></div>}
        <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={closeMode}>Cancel</button><button className="btn btn-primary" disabled={busy || allocationTotal > Number(receiptForm.amount || 0)}>{busy ? "Recording…" : "Record receipt"}</button></div>
      </form>}
      <div className="list-tools"><div className="search-box"><FileText size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search invoices…"/></div><span>{filteredInvoices.length} invoices</span></div>
      <div className="receivable-invoice-list">{filteredInvoices.map(row => <article className="receivable-invoice" key={row.id}>
        <button className="receivable-invoice-head" onClick={() => setSelectedInvoice(selectedInvoice === row.id ? "" : row.id)}><span><b>{row.invoice_number || `Draft ${row.id.slice(0, 8)}`}</b><small>{customers.find(customer => customer.id === row.customer_id)?.legal_name || row.customer_id} · Due {row.due_date}</small></span><b>{money(row.total, row.currency)}</b><span className={`status status-${(row.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{row.status}</span></button>
        {selectedInvoice === row.id && <div className="receivable-invoice-detail">
          <div className="receivable-detail-meta"><span>Outstanding <b>{money(row.outstanding, row.currency)}</b></span><span>Paid <b>{money(row.amount_paid, row.currency)}</b></span><span>Version <b>{row.version}</b></span></div>
          <div className="table-wrap"><table><thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Tax</th><th>Total</th></tr></thead><tbody>{(row.lines || []).map(line => <tr key={line.id}><td>{line.description}</td><td>{line.quantity}</td><td>{money(line.unit_price, row.currency)}</td><td>{money(line.tax_amount, row.currency)}</td><td>{money(line.line_total, row.currency)}</td></tr>)}</tbody></table></div>
          {canIssue && row.status === "Draft" && <div className="receivable-issue"><label>Issue reason<input value={issueReason[row.id] || ""} onChange={e => setIssueReason(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Reason for issuing this invoice"/></label><button className="btn btn-primary" disabled={busy || (issueReason[row.id] || "").trim().length < 3} onClick={() => issue(row)}><Send size={14}/>Issue invoice</button></div>}
        </div>}
      </article>)}{!filteredInvoices.length && <div className="empty-state">No invoices match this search.</div>}</div>
    </section>
    <section className="panel list-panel"><div className="list-heading"><div><h2>Receipt register</h2><p>Recorded receipts and their applied/unapplied balances.</p></div><span>{receipts.length} receipts</span></div>
      <div className="table-wrap"><table><thead><tr><th>Received</th><th>Customer</th><th>Reference</th><th>Amount</th><th>Applied</th><th>Unapplied</th></tr></thead><tbody>{receipts.map(row => <tr key={row.id}><td>{row.received_date}</td><td>{customers.find(customer => customer.id === row.customer_id)?.legal_name || row.customer_id}</td><td>{row.reference || "—"}</td><td>{money(row.amount, row.currency)}</td><td>{money(row.applied_amount, row.currency)}</td><td>{money(row.unapplied_amount, row.currency)}</td></tr>)}</tbody></table>{!receipts.length && <div className="empty-state">No receipts recorded yet.</div>}</div>
    </section>
  </div>;
}
