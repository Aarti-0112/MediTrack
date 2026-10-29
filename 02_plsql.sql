-- Run each block (ending with /) separately, or as a script.

---------------------------------------------------------------
-- 1. CURSOR: identify near-expiry batches (explicit cursor)
---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE proc_near_expiry_report (
    p_days IN NUMBER DEFAULT 30
) AS
    CURSOR c_near IS
        SELECT b.batch_id, b.batch_no, m.name, b.expiry_date, b.quantity,
               b.expiry_date - TRUNC(SYSDATE) AS days_left
        FROM   batches b
        JOIN   medicines m ON m.medicine_id = b.medicine_id
        WHERE  b.status = 'ACTIVE'
        AND    b.quantity > 0
        AND    b.expiry_date <= TRUNC(SYSDATE) + p_days
        ORDER  BY b.expiry_date;
    v_count NUMBER := 0;
BEGIN
    FOR r IN c_near LOOP
        v_count := v_count + 1;
        IF r.days_left < 0 THEN
            DBMS_OUTPUT.PUT_LINE('EXPIRED     : ' || r.name || ' | ' || r.batch_no ||
                                 ' | qty ' || r.quantity);
            -- move expired stock out (trigger will audit the change)
            INSERT INTO stock_movements (batch_id, movement_type, qty_change, remarks)
            VALUES (r.batch_id, 'EXPIRED', -r.quantity, 'Auto: batch expired');
            UPDATE batches SET quantity = 0, status = 'EXPIRED'
            WHERE  batch_id = r.batch_id;
        ELSE
            DBMS_OUTPUT.PUT_LINE('NEAR EXPIRY : ' || r.name || ' | ' || r.batch_no ||
                                 ' | ' || r.days_left || ' day(s) left | qty ' || r.quantity);
        END IF;
    END LOOP;
    DBMS_OUTPUT.PUT_LINE(v_count || ' batch(es) found.');
END proc_near_expiry_report;
/

-- Same query returned as a REF CURSOR so Python can read it
CREATE OR REPLACE FUNCTION get_near_expiry (p_days IN NUMBER)
RETURN SYS_REFCURSOR AS
    c SYS_REFCURSOR;
BEGIN
    OPEN c FOR
        SELECT b.batch_id, b.batch_no, m.name, b.expiry_date, b.quantity,
               b.expiry_date - TRUNC(SYSDATE) AS days_left
        FROM   batches b
        JOIN   medicines m ON m.medicine_id = b.medicine_id
        WHERE  b.status = 'ACTIVE'
        AND    b.quantity > 0
        AND    b.expiry_date <= TRUNC(SYSDATE) + p_days
        ORDER  BY b.expiry_date;
    RETURN c;
END;
/

---------------------------------------------------------------
-- 2. PROCEDURE: stock in / out
---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE proc_stock_movement (
    p_batch_id IN NUMBER,
    p_type     IN VARCHAR2,      -- 'IN' or 'OUT'
    p_qty      IN NUMBER,
    p_remarks  IN VARCHAR2 DEFAULT NULL
) AS
    v_status batches.status%TYPE;
    v_qty    batches.quantity%TYPE;
BEGIN
    IF p_qty <= 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Quantity must be positive.');
    END IF;
    IF p_type NOT IN ('IN','OUT') THEN
        RAISE_APPLICATION_ERROR(-20002, 'Type must be IN or OUT.');
    END IF;

    SELECT status, quantity INTO v_status, v_qty
    FROM   batches WHERE batch_id = p_batch_id FOR UPDATE;

    IF v_status <> 'ACTIVE' THEN
        RAISE_APPLICATION_ERROR(-20003, 'Batch is ' || v_status || '; no movement allowed.');
    END IF;
    IF p_type = 'OUT' AND p_qty > v_qty THEN
        RAISE_APPLICATION_ERROR(-20004, 'Insufficient stock. Available: ' || v_qty);
    END IF;

    UPDATE batches
    SET    quantity = quantity + CASE p_type WHEN 'IN' THEN p_qty ELSE -p_qty END
    WHERE  batch_id = p_batch_id;

    INSERT INTO stock_movements (batch_id, movement_type, qty_change, remarks)
    VALUES (p_batch_id, p_type, CASE p_type WHEN 'IN' THEN p_qty ELSE -p_qty END, p_remarks);
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20005, 'Batch not found.');
END proc_stock_movement;
/

---------------------------------------------------------------
-- 3. PROCEDURE: process a batch recall
---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE process_batch_recall (
    p_batch_id IN NUMBER,
    p_reason   IN VARCHAR2
) AS
    v_status batches.status%TYPE;
    v_qty    batches.quantity%TYPE;
BEGIN
    SELECT status, quantity INTO v_status, v_qty
    FROM   batches WHERE batch_id = p_batch_id FOR UPDATE;

    IF v_status = 'RECALLED' THEN
        RAISE_APPLICATION_ERROR(-20006, 'Batch is already recalled.');
    END IF;

    INSERT INTO recalls (batch_id, reason, qty_recalled)
    VALUES (p_batch_id, p_reason, v_qty);

    INSERT INTO stock_movements (batch_id, movement_type, qty_change, remarks)
    VALUES (p_batch_id, 'RECALL', -v_qty, p_reason);

    UPDATE batches SET quantity = 0, status = 'RECALLED'
    WHERE  batch_id = p_batch_id;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20005, 'Batch not found.');
END process_batch_recall;
/

---------------------------------------------------------------
-- 4. TRIGGER: record every stock change
---------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_batch_stock_audit
AFTER INSERT OR UPDATE OF quantity ON batches
FOR EACH ROW
BEGIN
    IF INSERTING THEN
        INSERT INTO stock_audit (batch_id, old_qty, new_qty, action, changed_by)
        VALUES (:NEW.batch_id, 0, :NEW.quantity, 'INSERT',
                SYS_CONTEXT('USERENV','SESSION_USER'));
    ELSIF :NEW.quantity <> :OLD.quantity THEN
        INSERT INTO stock_audit (batch_id, old_qty, new_qty, action, changed_by)
        VALUES (:NEW.batch_id, :OLD.quantity, :NEW.quantity, 'UPDATE',
                SYS_CONTEXT('USERENV','SESSION_USER'));
    END IF;
END;
/
