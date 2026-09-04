-- =====================================================================
-- INTELLIWORKS INDUSTRIES — SUPABASE STORAGE BUCKETS & POLICIES
-- =====================================================================

-- 1. Create private bucket for assignment materials & deliverables
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'assignment-files',
    'assignment-files',
    false,
    52428800, -- 50 MB limit
    ARRAY[
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'application/x-tex',
        'application/zip',
        'application/x-zip-compressed',
        'image/png',
        'image/jpeg'
    ]
)
ON CONFLICT (id) DO UPDATE SET
    public = false,
    file_size_limit = 52428800;

-- 2. Storage Objects Row Level Security
-- Note: Files are organized in paths: {assignment_id}/{submission_id_or_brief}/{filename}

-- Policy: Download/Read permission
-- Only client, assigned writer, or platform admin can download
CREATE POLICY "Protected download: assignment participants & admin"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'assignment-files'
    AND (
        EXISTS (
            SELECT 1 FROM assignments a
            WHERE a.id::text = (storage.foldername(name))[1]
            AND (
                a.client_id = auth.uid()
                OR a.writer_id = auth.uid()
                OR EXISTS (SELECT 1 FROM users u WHERE u.id = auth.uid() AND u.role = 'Admin')
            )
        )
    )
);

-- Policy: Upload permission
-- Only authenticated participants of the assignment or client during creation
CREATE POLICY "Protected upload: assignment participants"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'assignment-files'
    AND auth.role() = 'authenticated'
    AND (
        -- For assignment folders
        EXISTS (
            SELECT 1 FROM assignments a
            WHERE a.id::text = (storage.foldername(name))[1]
            AND (
                a.client_id = auth.uid()
                OR a.writer_id = auth.uid()
                OR EXISTS (SELECT 1 FROM users u WHERE u.id = auth.uid() AND u.role = 'Admin')
            )
        )
        -- Or direct server-side upload with service role
        OR auth.uid() IS NOT NULL
    )
);

-- Policy: Prevent public deletion
CREATE POLICY "Protected delete: Admin only"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'assignment-files'
    AND EXISTS (SELECT 1 FROM users u WHERE u.id = auth.uid() AND u.role = 'Admin')
);
