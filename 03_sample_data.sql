INSERT INTO medicines (name, manufacturer, category) VALUES ('Paracetamol 500mg','Sun Pharma','Analgesic');
INSERT INTO medicines (name, manufacturer, category) VALUES ('Amoxicillin 250mg','Cipla','Antibiotic');
INSERT INTO medicines (name, manufacturer, category) VALUES ('Cetirizine 10mg','Dr. Reddys','Antihistamine');

INSERT INTO batches (medicine_id, batch_no, mfg_date, expiry_date, quantity)
VALUES (1,'PCM-001', TRUNC(SYSDATE)-300, TRUNC(SYSDATE)+20, 200);
INSERT INTO batches (medicine_id, batch_no, mfg_date, expiry_date, quantity)
VALUES (2,'AMX-001', TRUNC(SYSDATE)-400, TRUNC(SYSDATE)-5, 80);
INSERT INTO batches (medicine_id, batch_no, mfg_date, expiry_date, quantity)
VALUES (3,'CTZ-001', TRUNC(SYSDATE)-100, TRUNC(SYSDATE)+400, 150);
COMMIT;
