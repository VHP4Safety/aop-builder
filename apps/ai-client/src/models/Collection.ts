export interface Collection {
    id: number,
    user_id: number,
    name: string,
    description: string,
    created_at: string,
    pdf_ids: number[],
    total_chunks: number,
    status: 'unscanned' | 'pre_processing' | 'chunking' | 'scanned' | 'queued_preprocessing'
}