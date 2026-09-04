-- =====================================================================
-- INTELLIWORKS INDUSTRIES — MASTER POSTGRESQL DATABASE SCHEMA
-- Compatible with Supabase PostgreSQL (auth.users integration & RLS)
-- =====================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean existing if re-running
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS disputes CASCADE;
DROP TABLE IF EXISTS withdrawals CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS submissions CASCADE;
DROP TABLE IF EXISTS assignments CASCADE;
DROP TABLE IF EXISTS referrals CASCADE;
DROP TABLE IF EXISTS platform_settings CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ---------------------------------------------------------------------
-- 1. USERS PROFILE TABLE (Tied to Supabase Auth UUID)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Client', 'Writer', 'Admin')),
    account_status TEXT NOT NULL DEFAULT 'Active' CHECK (account_status IN ('Active', 'Suspended', 'Pending Approval', 'Deactivated')),
    profile_photo TEXT,
    bio TEXT,
    skills TEXT[] DEFAULT '{}',
    referral_code TEXT UNIQUE NOT NULL,
    total_earnings NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total_earnings >= 0),
    total_spent NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total_spent >= 0),
    available_balance NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (available_balance >= 0),
    average_rating NUMERIC(3, 2) NOT NULL DEFAULT 0.00 CHECK (average_rating >= 0 AND average_rating <= 5.00),
    total_reviews INT NOT NULL DEFAULT 0 CHECK (total_reviews >= 0),
    academic_agreement_accepted BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_referral_code ON users(referral_code);

-- ---------------------------------------------------------------------
-- 2. PLATFORM SETTINGS
-- ---------------------------------------------------------------------
CREATE TABLE platform_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES users(id)
);

-- Seed default platform parameters (80/20 escrow split, 5% referral, $20 min withdrawal)
INSERT INTO platform_settings (key, value, description) VALUES
('escrow_split', '{"writer_percentage": 80.0, "platform_fee_percentage": 20.0}'::jsonb, 'Standard 80/20 platform escrow distribution'),
('referral_percentage', '5.0'::jsonb, 'Referral commission percentage paid to referring user'),
('minimum_withdrawal', '20.00'::jsonb, 'Minimum withdrawal balance required for payout requests'),
('maintenance_mode', 'false'::jsonb, 'Platform-wide maintenance toggle');

-- ---------------------------------------------------------------------
-- 3. ASSIGNMENTS TABLE & STATE MACHINE
-- ---------------------------------------------------------------------
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    writer_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    word_count INT NOT NULL CHECK (word_count >= 0),
    budget NUMERIC(12, 2) NOT NULL CHECK (budget > 0),
    deadline TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN (
        'Open', 'Claimed', 'Submitted', 'Revision Requested', 'Approved', 'Cancelled', 'Disputed'
    )),
    revision_count INT NOT NULL DEFAULT 0 CHECK (revision_count >= 0),
    escrow_status TEXT NOT NULL DEFAULT 'Funded' CHECK (escrow_status IN (
        'Pending', 'Funded', 'Released', 'Refunded', 'Disputed'
    )),
    writer_payout NUMERIC(12, 2) NOT NULL CHECK (writer_payout >= 0),
    platform_fee NUMERIC(12, 2) NOT NULL CHECK (platform_fee >= 0),
    academic_integrity_declaration BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assignments_client ON assignments(client_id);
CREATE INDEX idx_assignments_writer ON assignments(writer_id);
CREATE INDEX idx_assignments_status ON assignments(status);
CREATE INDEX idx_assignments_deadline ON assignments(deadline);
CREATE INDEX idx_assignments_category ON assignments(category);

-- ---------------------------------------------------------------------
-- 4. SUBMISSIONS TABLE
-- ---------------------------------------------------------------------
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    writer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    revision_number INT NOT NULL CHECK (revision_number >= 1),
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'Submitted' CHECK (status IN (
        'Submitted', 'Under Review', 'Revision Requested', 'Accepted'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_assignment_revision UNIQUE (assignment_id, revision_number)
);

CREATE INDEX idx_submissions_assignment ON submissions(assignment_id);

-- ---------------------------------------------------------------------
-- 5. FILES METADATA TABLE (Supabase Storage reference)
-- ---------------------------------------------------------------------
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    submission_id UUID REFERENCES submissions(id) ON DELETE SET NULL,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,
    size BIGINT NOT NULL CHECK (size > 0),
    file_category TEXT NOT NULL CHECK (file_category IN ('Brief', 'Draft', 'Deliverable', 'Proof', 'Supporting')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_files_assignment ON files(assignment_id);
CREATE INDEX idx_files_submission ON files(submission_id);

-- ---------------------------------------------------------------------
-- 6. TRANSACTIONS LEDGER (Immutable Double-Entry Style Records)
-- ---------------------------------------------------------------------
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assignment_id UUID REFERENCES assignments(id) ON DELETE SET NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN (
        'Escrow Deposit', 'Writer Payout', 'Platform Fee', 'Refund', 'Referral Bonus', 'Withdrawal'
    )),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount != 0),
    status TEXT NOT NULL DEFAULT 'Completed' CHECK (status IN ('Pending', 'Completed', 'Failed')),
    reference TEXT,
    idempotency_key TEXT UNIQUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_transactions_assignment ON transactions(assignment_id);
CREATE INDEX idx_transactions_type ON transactions(transaction_type);

-- ---------------------------------------------------------------------
-- 7. WITHDRAWALS TABLE
-- ---------------------------------------------------------------------
CREATE TABLE withdrawals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN (
        'Pending', 'Approved', 'Rejected', 'Cancelled'
    )),
    payout_method TEXT NOT NULL,
    account_details TEXT NOT NULL,
    admin_notes TEXT,
    processed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_withdrawals_user ON withdrawals(user_id);
CREATE INDEX idx_withdrawals_status ON withdrawals(status);

-- ---------------------------------------------------------------------
-- 8. DISPUTES TABLE
-- ---------------------------------------------------------------------
CREATE TABLE disputes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL UNIQUE REFERENCES assignments(id) ON DELETE RESTRICT,
    opened_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    opposing_party UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Under Review', 'Resolved', 'Dismissed')),
    settlement_type TEXT CHECK (settlement_type IN (
        'Full Release to Writer', 'Full Refund to Client', '50/50 Settlement', 'Dismiss'
    )),
    admin_notes TEXT,
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_disputes_assignment ON disputes(assignment_id);
CREATE INDEX idx_disputes_status ON disputes(status);

-- ---------------------------------------------------------------------
-- 9. REVIEWS TABLE
-- ---------------------------------------------------------------------
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL UNIQUE REFERENCES assignments(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    writer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    feedback TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_no_self_review CHECK (client_id != writer_id)
);

CREATE INDEX idx_reviews_writer ON reviews(writer_id);

-- ---------------------------------------------------------------------
-- 10. ASSIGNMENT-SCOPED MESSAGING
-- ---------------------------------------------------------------------
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    message TEXT NOT NULL,
    attachment_id UUID REFERENCES files(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_assignment ON messages(assignment_id);

-- ---------------------------------------------------------------------
-- 11. NOTIFICATIONS
-- ---------------------------------------------------------------------
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    related_assignment_id UUID REFERENCES assignments(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_recipient ON notifications(recipient_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);

-- ---------------------------------------------------------------------
-- 12. REFERRALS TABLE
-- ---------------------------------------------------------------------
CREATE TABLE referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    referred_user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    referral_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Rewarded')),
    commission_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rewarded_at TIMESTAMPTZ,
    CONSTRAINT chk_no_self_referral CHECK (referrer_id != referred_user_id)
);

CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);

-- ---------------------------------------------------------------------
-- 13. AUDIT LOGS (Immutable Security Records)
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    http_method TEXT,
    route TEXT,
    ip_address TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- ---------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ---------------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE withdrawals ENABLE ROW LEVEL SECURITY;
ALTER TABLE disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to check if user is Admin
CREATE OR REPLACE FUNCTION is_admin(user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM users WHERE id = user_id AND role = 'Admin');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Users RLS
CREATE POLICY "Users can read own profile or admin reads all"
    ON users FOR SELECT
    USING (auth.uid() = id OR is_admin(auth.uid()));

CREATE POLICY "Users can update own bio/photo, admins update all"
    ON users FOR UPDATE
    USING (auth.uid() = id OR is_admin(auth.uid()));

-- Assignments RLS
CREATE POLICY "Anyone authenticated can view Open assignments, or participants view own"
    ON assignments FOR SELECT
    USING (
        status = 'Open'
        OR client_id = auth.uid()
        OR writer_id = auth.uid()
        OR is_admin(auth.uid())
    );

CREATE POLICY "Clients can create assignments"
    ON assignments FOR INSERT
    WITH CHECK (auth.uid() = client_id);

-- Submissions RLS
CREATE POLICY "Submission access by assignment participants and admin"
    ON submissions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM assignments a
            WHERE a.id = submissions.assignment_id
            AND (a.client_id = auth.uid() OR a.writer_id = auth.uid() OR is_admin(auth.uid()))
        )
    );

-- Files RLS
CREATE POLICY "File access by assignment participants and admin"
    ON files FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM assignments a
            WHERE a.id = files.assignment_id
            AND (a.client_id = auth.uid() OR a.writer_id = auth.uid() OR is_admin(auth.uid()))
        )
    );

-- Transactions RLS
CREATE POLICY "Users can view own transactions, admin views all"
    ON transactions FOR SELECT
    USING (user_id = auth.uid() OR is_admin(auth.uid()));

-- Withdrawals RLS
CREATE POLICY "Users can view and create own withdrawals, admin views all"
    ON withdrawals FOR SELECT
    USING (user_id = auth.uid() OR is_admin(auth.uid()));

CREATE POLICY "Users can request withdrawals"
    ON withdrawals FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Disputes RLS
CREATE POLICY "Dispute access for participants and admin"
    ON disputes FOR SELECT
    USING (opened_by = auth.uid() OR opposing_party = auth.uid() OR is_admin(auth.uid()));

-- Messages RLS
CREATE POLICY "Messages access by assignment participants and admin"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM assignments a
            WHERE a.id = messages.assignment_id
            AND (a.client_id = auth.uid() OR a.writer_id = auth.uid() OR is_admin(auth.uid()))
        )
    );

-- Notifications RLS
CREATE POLICY "Users can view and update own notifications"
    ON notifications FOR ALL
    USING (recipient_id = auth.uid());

-- Audit logs: read-only for Admin, no direct modifications
CREATE POLICY "Only admins can view audit logs"
    ON audit_logs FOR SELECT
    USING (is_admin(auth.uid()));

-- Platform settings: read for all authenticated, write for admin only
CREATE POLICY "Platform settings read by authenticated"
    ON platform_settings FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Platform settings update by admin only"
    ON platform_settings FOR ALL
    USING (is_admin(auth.uid()));
