# CHAIN Supabase Storage Buckets

This document outlines the required Supabase Storage buckets for the CHAIN application Phase 6.

## Required Buckets

The following buckets must be created manually in the Supabase Dashboard:

| Bucket Name | Public | Usage |
|-------------|--------|-------|
| `chain-avatars` | Yes | Profile avatars |
| `chain-covers` | Yes | Profile and album covers |
| `chain-stories` | Yes | User stories (images/videos) |
| `chain-marketplace` | Yes | Marketplace item media and previews |
| `chain-music` | Yes | Music track audio files |
| `chain-videos` | Yes | General video uploads |
| `chain-payment-proofs` | No | Wallet top-up transaction proofs |
| `chain-verifications` | No | User ID and selfie verification documents |

## Manual Setup Instructions

1.  Log in to your [Supabase Dashboard](https://app.supabase.com/).
2.  Go to the **Storage** section in the left sidebar.
3.  Click **New bucket** for each item in the list above.
4.  Toggle the **Public bucket** switch according to the table above.
5.  Set the **Allowed MIME types** (optional but recommended):
    -   Images: `image/*`
    -   Audio: `audio/*`
    -   Video: `video/*`
    -   Documents: `application/pdf`, `image/*`

## Security Policies (RLS)

It is highly recommended to set up Row Level Security (RLS) policies for each bucket.

### Public Buckets (e.g., `chain-avatars`)
-   **Select**: Allow for everyone (`anon`, `authenticated`).
-   **Insert/Update/Delete**: Allow only for `authenticated` users where `owner` matches their `auth.uid()`.

### Private Buckets (e.g., `chain-verifications`)
-   **Select**: Allow only for `authenticated` users where `owner` matches their `auth.uid()` OR for users with `admin` role.
-   **Insert**: Allow for `authenticated` users.
-   **Update/Delete**: Restricted or limited to `admin` role.

## Usage in Code

The `services/storage_service.py` handles the interaction with these buckets using the `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` defined in your `.env` file.
