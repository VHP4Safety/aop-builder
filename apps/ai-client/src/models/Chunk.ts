export interface Chunk {
    chunk_id: string;
    chunk: string;         // De tekst van de chunk
    heading: string;       // De kop/titel van de chunk
    document_id: string;   // De ID van het document waar de chunk bij hoort
    score: number;         // De relevantie score van de chunk
    selected?: boolean;    // Geeft aan of de chunk is geselecteerd voor analyse
}