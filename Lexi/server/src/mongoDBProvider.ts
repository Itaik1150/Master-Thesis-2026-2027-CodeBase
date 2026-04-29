// MongoDbProvider.ts

import dotenv from 'dotenv';
import mongoose from 'mongoose';

dotenv.config();

class MongoDbProvider {
    constructor() {
        console.log('Create MongoDbProvider');
    }

    private initializeConnection() {
        const uri = `${process.env.MONGODB_URL}/${process.env.MONGODB_DB_NAME}`;
        console.log('Connecting to MongoDB...');
        mongoose
            .connect(uri)
            .then(() => {
                console.log('Successfully connected to MongoDB');
            })
            .catch((err) => {
                console.error('Could not connect to MongoDB...', err);
            });
    }

    public initialize() {
        this.initializeConnection();
    }

    public getModel<T>(modelName: string, schema: mongoose.Schema<T>): mongoose.Model<T> {
        if (mongoose.models[modelName]) {
            return mongoose.model<T>(modelName);
        }
        return mongoose.model<T>(modelName, schema);
    }
}

export const mongoDbProvider = new MongoDbProvider();
