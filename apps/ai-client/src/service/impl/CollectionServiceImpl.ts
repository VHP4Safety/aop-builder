import axios from 'axios';
import {CollectionService} from "../CollectionService.ts";
import {Collection} from "../../models/Collection.ts";

export class CollectionServiceImpl implements CollectionService
{
    async create(name: string, description: string): Promise<Collection>
    {
        try {
            const response = await axios.post('/collections/', {
                name: name,
                description: description,
            })

            return response.data
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het aanmaken van een collectie.');
        }
    }

    async getCollections(): Promise<Collection[]>
    {
        try {
            const response = await axios.get('/collections/')

            return response.data
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het ophalen van alle collecties.');
        }
    }

    async scanCollection(id: number): Promise<any>
    {
        try {
            const response = await axios.post(`/collections/${id}/scan`)

            return response.data
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het ophalen van alle collecties.');
        }
    }


    async uploadPdfDocument(collectionId: number, file: File): Promise<any>
    {
        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await axios.post(`/collections/${collectionId}/upload`, formData);
            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het uploaden van een pdf document.');
        }
    }

}

export const collectionService = new CollectionServiceImpl();
