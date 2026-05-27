import {Chunk} from "./Chunk.ts";

export interface CollectionDocument {
    document_id: string;   // De unieke ID van het document
    name: string;
    chunks: Chunk[];       // De lijst van chunks binnen het document
    expanded?: boolean;    // UI state: of het document open/gesloten is
    done?: boolean;        // UI state: of het document is verwerkt
    threshold?: number;    // Drempelwaarde voor geselecteerde chunks
}