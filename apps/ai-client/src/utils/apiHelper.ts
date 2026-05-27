import axios, { AxiosResponse } from 'axios';

async function fetchData<T>(promise: Promise<AxiosResponse<T>>): Promise<T> {
    let response;
    try {
        response = await promise;
    } catch (err) {
        if (axios.isAxiosError(err)) {
            throw err.response ? err.response.data : err;
        }
        throw err;
    }

    if (!response) {
        throw new Error('No response received');
    }

    return response.data;
}

export default fetchData;
