import { Log } from "./Log.ts";
import {CollectionDocument} from "./CollectionDocument.ts";

export interface CausalRelation {
    subject: string;
    object: string;
    verb: string;
    causal_connection: "Positive" | "Negative" | "Not existing";
    [key: string]: any; // optioneel
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
    logs: Log[];
    documents: CollectionDocument[];
    extracted_causal_relations?: {
        output?: {
            relationships?: CausalRelation[];
        };
    }[];
}
