export interface SessionLog {
    id: number;
    timestamp: string;
    status: string;
}

export interface SessionTelemetry {
    phase?: string;
    model_name?: string;
    total_chunks: number;
    processed_chunks: number;
    successful_chunks: number;
    failed_chunks: number;
    total_relationships: number;
    percent_complete: number;
    started_at?: string;
    updated_at?: string;
    last_chunk_id?: string;
    last_message?: string;
    last_error?: string;
}

export interface Session {
    user_id: number;
    collection_id: number;
    title: string;
    key_events: string[];
    model_name: string;
    relevance_score_threshold: number;
    id: number;
    status: string;
    created_at: string;
    updated_at: string;
    logs: SessionLog[];
    telemetry?: SessionTelemetry | null;
    documents: any[]; // Eventueel vervangen door specifiek type als je die hebt
}

export interface Chunk {
    id: string;
    text: string;
    relevance: number;
    selected: boolean;
    tokens: number;
}

export interface SelectedChunkGroup {
    document_id: string;
    name: string;
    reference?: {
        document_id?: string;
        filename?: string;
        title?: string;
        authors?: string | null;
        subject?: string | null;
        keywords?: string | null;
        doi?: string | null;
        year?: number | null;
        upload_date?: string | null;
        content_type?: string | null;
        file_size_bytes?: number | null;
        page_count?: number | null;
    };
    chunks: Chunk[];
}

export type CausalConnection = "Positive" | "Negative" | "Not existing";

export interface CausalRelation {
    subject: string;
    verb: string;
    object: string;
    causal_connection: CausalConnection;
}

export interface CausalRelationOutput {
    relationships: CausalRelation[];
}

export interface ExtractedCausalRelation {
    id: string;
    text: string;
    output: CausalRelationOutput;
}

export interface EnrichedOntologyTerm {
    label?: string;
    curie?: string;
    iri?: string;
    ontology_name?: string;
    description?: string | null;
    is_defining_ontology?: boolean;
    match_score?: number;
}

export interface EnrichedAopLink {
    url: string;
    label: string;
}

export interface EnrichedGraphNode {
    id: string;
    raw_label: string;
    display_label: string;
    normalized_label: string;
    ontology_term?: EnrichedOntologyTerm | null;
    aop_wiki_links?: EnrichedAopLink[];
}

export interface EnrichedGraphEvidence {
    chunk_id?: string;
    chunk_text?: string;
    document_name?: string;
}

export interface EnrichedGraphEdge {
    id: string;
    source: string;
    target: string;
    source_label: string;
    target_label: string;
    predicate: string;
    causal_connection: CausalConnection;
    evidence: EnrichedGraphEvidence[];
}

export interface EnrichedGraphSummary {
    raw_relationships: number;
    standardized_nodes: number;
    standardized_edges: number;
    nodes_with_ontology_match: number;
    nodes_with_aop_links: number;
}

export interface EnrichedGraph {
    session_id: number;
    created_at: string;
    nodes: EnrichedGraphNode[];
    edges: EnrichedGraphEdge[];
    summary: EnrichedGraphSummary;
    provenance?: {
        ols_base_url?: string | null;
        aop_mcp_base_url?: string | null;
    };
}

export interface SessionWithResultResponse {
    session: Session;
    selected_chunks: SelectedChunkGroup[];
    extracted_causal_relations: ExtractedCausalRelation[];
    enriched_graph?: EnrichedGraph | null;
}
