-- =====================================================================
-- INTELLIWORKS INDUSTRIES — DEVELOPMENT / TEST DATABASE SEEDING
-- WARNING: This is strictly for development/test environments.
-- Real production accounts MUST authenticate through Supabase Auth.
-- =====================================================================

-- Verify platform settings are populated
INSERT INTO platform_settings (key, value, description)
VALUES 
    ('escrow_split', '{"writer_percentage": 80.0, "platform_fee_percentage": 20.0}'::jsonb, 'Standard 80/20 platform escrow distribution'),
    ('referral_percentage', '5.0'::jsonb, 'Referral commission percentage paid to referring user'),
    ('minimum_withdrawal', '20.00'::jsonb, 'Minimum withdrawal balance required for payout requests'),
    ('maintenance_mode', 'false'::jsonb, 'Platform-wide maintenance toggle')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Note for developers:
-- In Supabase, to seed test users, create them in the Supabase Auth Dashboard
-- or via the frontend registration screen. The application's server-side
-- auto-provisioning hook will insert the corresponding record in `public.users`
-- ensuring foreign-key integrity with `auth.users(id)`.
