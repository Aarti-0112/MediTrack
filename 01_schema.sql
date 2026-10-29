-- Run this first (FreeSQL / Oracle 12c+)
CREATE TABLE medicines (
    medicine_id  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR2(100) NOT NULL,
    manufacturer VARCHAR2(100),
    category     VARCHAR2(50)
);

CREATE TABLE batches (
    batch_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicine_id  NUMBER NOT NULL REFERENCES medicines(medicine_id),
    batch_no     VARCHAR2(30) NOT NULL UNIQUE,
    mfg_date     DATE NOT NULL,
    expiry_date  DATE NOT NULL,
    quantity     NUMBER DEFAULT 0 NOT NULL CHECK (quantity >= 0),
    status       VARCHAR2(10) DEFAULT 'ACTIVE'
                 CHECK (status IN ('ACTIVE','RECALLED','EXPIRED')),
    CONSTRAINT chk_batch_dates CHECK (expiry_date > mfg_date)
);

CREATE TABLE recalls (
    recall_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id     NUMBER NOT NULL REFERENCES batches(batch_id),
    reason       VARCHAR2(300) NOT NULL,
    qty_recalled NUMBER NOT NULL,
    recall_date  DATE DEFAULT SYSDATE
);

CREATE TABLE stock_movements (
    movement_id   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id      NUMBER NOT NULL REFERENCES batches(batch_id),
    movement_type VARCHAR2(10) NOT NULL
                  CHECK (movement_type IN ('IN','OUT','RECALL','EXPIRED')),
    qty_change    NUMBER NOT NULL,          -- +ve for IN, -ve for others
    remarks       VARCHAR2(200),
    moved_on      DATE DEFAULT SYSDATE
);

-- filled automatically by the trigger
CREATE TABLE stock_audit (
    audit_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id    NUMBER NOT NULL,
    old_qty     NUMBER,
    new_qty     NUMBER,
    action      VARCHAR2(10),
    changed_by  VARCHAR2(50),
    changed_on  TIMESTAMP DEFAULT SYSTIMESTAMP
);
