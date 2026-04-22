-- GreenField Arena - MySQL schema (tables, triggers, cursors, procedures)
DROP DATABASE IF EXISTS turf_booking;
CREATE DATABASE turf_booking CHARACTER SET utf8mb4;
USE turf_booking;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    whatsapp VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);
CREATE TABLE bookings (
    id VARCHAR(20) PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    whatsapp VARCHAR(20) NOT NULL,
    booking_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('upcoming','completed','cancelled') DEFAULT 'upcoming',
    payment_method ENUM('card','upi','cash') DEFAULT 'upi',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_date_status (booking_date, status)
);
CREATE TABLE booking_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id VARCHAR(20) NOT NULL,
    slot_id VARCHAR(20) NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    INDEX idx_slot (slot_id)
);
CREATE TABLE booking_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id VARCHAR(20),
    action VARCHAR(40),
    detail VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id VARCHAR(20) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    method ENUM('card','upi','cash') DEFAULT 'upi',
    status ENUM('paid','refunded','failed') DEFAULT 'paid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
);

-- Placeholder admin (real hash set by seed_admin.py)
INSERT INTO admins (name, email, password_hash) VALUES
('Arena Admin', 'admin@greenfield.com', 'placeholder-run-seed-admin-py');

DELIMITER $$

-- TRIGGER: prevent double-booking same date+slot
CREATE TRIGGER trg_prevent_double_booking
BEFORE INSERT ON booking_slots
FOR EACH ROW
BEGIN
    DECLARE clash INT DEFAULT 0;
    DECLARE bdate DATE;
    SELECT booking_date INTO bdate FROM bookings WHERE id = NEW.booking_id;
    SELECT COUNT(*) INTO clash
      FROM booking_slots bs
      JOIN bookings b ON b.id = bs.booking_id
     WHERE b.booking_date = bdate
       AND bs.slot_id = NEW.slot_id
       AND b.status <> 'cancelled'
       AND bs.booking_id <> NEW.booking_id;
    IF clash > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Slot already booked for this date';
    END IF;
END$$

-- TRIGGER: audit logs
CREATE TRIGGER trg_log_booking_insert
AFTER INSERT ON bookings FOR EACH ROW
BEGIN
    INSERT INTO booking_logs(booking_id, action, detail)
    VALUES (NEW.id, 'CREATED', CONCAT('user=', NEW.user_id, ' date=', NEW.booking_date));
END$$

CREATE TRIGGER trg_log_booking_update
AFTER UPDATE ON bookings FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO booking_logs(booking_id, action, detail)
        VALUES (NEW.id, 'STATUS', CONCAT(OLD.status, ' -> ', NEW.status));
    END IF;
END$$

CREATE FUNCTION gen_booking_id() RETURNS VARCHAR(20)
DETERMINISTIC NO SQL
RETURN CONCAT('GFA-', UPPER(SUBSTRING(MD5(RAND()), 1, 5)));

-- PROCEDURE: BookSlot - splits CSV, atomic insert
CREATE PROCEDURE BookSlot(
    IN p_user_id INT, IN p_name VARCHAR(100), IN p_whatsapp VARCHAR(20),
    IN p_date DATE, IN p_slot_csv TEXT, IN p_amount DECIMAL(10,2),
    IN p_payment_method VARCHAR(10), OUT p_booking_id VARCHAR(20)
)
BEGIN
    DECLARE v_slot VARCHAR(20);
    DECLARE v_remaining TEXT DEFAULT p_slot_csv;
    DECLARE v_pos INT;
    SET p_booking_id = gen_booking_id();
    INSERT INTO bookings(id,user_id,name,whatsapp,booking_date,amount,status,payment_method)
    VALUES (p_booking_id,p_user_id,p_name,p_whatsapp,p_date,p_amount,'upcoming',p_payment_method);
    WHILE LENGTH(v_remaining) > 0 DO
        SET v_pos = LOCATE(',', v_remaining);
        IF v_pos = 0 THEN SET v_slot = v_remaining; SET v_remaining = '';
        ELSE SET v_slot = SUBSTRING(v_remaining, 1, v_pos - 1);
             SET v_remaining = SUBSTRING(v_remaining, v_pos + 1); END IF;
        INSERT INTO booking_slots(booking_id, slot_id) VALUES (p_booking_id, v_slot);
    END WHILE;
    INSERT INTO payments(booking_id, amount, method, status)
    VALUES (p_booking_id, p_amount, p_payment_method, 'paid');
END$$

-- PROCEDURE: CancelBooking
CREATE PROCEDURE CancelBooking(IN p_booking_id VARCHAR(20), IN p_user_id INT, IN p_is_admin TINYINT)
BEGIN
    DECLARE v_owner INT; DECLARE v_status VARCHAR(20);
    SELECT user_id, status INTO v_owner, v_status FROM bookings WHERE id = p_booking_id;
    IF v_owner IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Booking not found'; END IF;
    IF p_is_admin = 0 AND v_owner <> p_user_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Not your booking'; END IF;
    IF v_status <> 'upcoming' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only upcoming bookings can be cancelled'; END IF;
    UPDATE bookings SET status='cancelled' WHERE id = p_booking_id;
    UPDATE payments SET status='refunded' WHERE booking_id = p_booking_id;
END$$

-- PROCEDURE: AutoCompleteBookings - past upcoming -> completed
CREATE PROCEDURE AutoCompleteBookings()
BEGIN
    UPDATE bookings SET status='completed'
     WHERE status='upcoming' AND booking_date < CURDATE();
END$$

-- PROCEDURE: GetRevenueReport - CURSOR-based aggregate
CREATE PROCEDURE GetRevenueReport()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_amount DECIMAL(10,2); DECLARE v_status VARCHAR(20);
    DECLARE v_total DECIMAL(12,2) DEFAULT 0;
    DECLARE v_up INT DEFAULT 0; DECLARE v_dn INT DEFAULT 0; DECLARE v_cn INT DEFAULT 0;
    DECLARE cur CURSOR FOR SELECT amount, status FROM bookings;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_amount, v_status;
        IF done = 1 THEN LEAVE read_loop; END IF;
        IF v_status='upcoming' THEN SET v_up=v_up+1; SET v_total=v_total+v_amount;
        ELSEIF v_status='completed' THEN SET v_dn=v_dn+1; SET v_total=v_total+v_amount;
        ELSE SET v_cn=v_cn+1; END IF;
    END LOOP;
    CLOSE cur;
    SELECT v_total AS revenue, v_up AS upcoming, v_dn AS completed,
           v_cn AS cancelled, (v_up+v_dn+v_cn) AS total_bookings;
END$$

DELIMITER ;
