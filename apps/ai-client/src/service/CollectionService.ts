import { Collection } from "../models/Collection.ts";

export interface CollectionService {
    create(name: string, description: string): Promise<Collection>;
    getCollections(): Promise<Collection[]>;
    scanCollection(id: number): Promise<any>;
    uploadPdfDocument(collectionId: number, file: File): Promise<any>;
}