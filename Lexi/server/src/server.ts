import bodyParser from 'body-parser';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import dotenv from 'dotenv';
import express from 'express';
import { mongoDbProvider } from './mongoDBProvider';
import { agentsRouter } from './routers/agentsRouter.router';
import { conversationsRouter } from './routers/conversationsRouter.router';
import { dataAggregationRouter } from './routers/dataAggregationRouter.router';
import { experimentsRouter } from './routers/experimentsRouter.router';
import { formsRouter } from './routers/formsRouter';
import { usersRouter } from './routers/usersRouter.router';
import { usersService } from './services/users.service';

dotenv.config();

mongoDbProvider.initialize();

const createAdminUser = (username: string, password: string) => {
    if (!username || !password) {
        console.warn('Username and password are required');
        process.exit(1);
    }

    usersService
        .createAdminUser(username, password)
        .then(() => {
            console.log('Admin user created successfully');
            process.exit(0);
        })
        .catch((error) => {
            console.error('Error creating admin user:', error);
            process.exit(1);
        });
};

const setupServer = () => {
    const app = express();
    app.use(bodyParser.json());
    const corsOptions = {
        origin: (origin, callback) => {
            const allowedOrigins = [
                process.env.FRONTEND_URL || 'http://localhost:3000',
                'https://master-thesis-2026-2027-code-base.vercel.app',  // production
                'http://10.0.2.2:3000',
                'http://127.0.0.1:3000',
                'http://0.0.0.0:3000',
                'http://192.168.31.200:3000',  // real phone WiFi testing (static IP)
            ];
            // Allow any Vercel preview URLs for this project
            const isVercelPreview = origin && origin.includes('master-thesis-2026-2027-code-base') && origin.endsWith('.vercel.app');
            if (!origin || allowedOrigins.includes(origin) || isVercelPreview) {
                callback(null, true);
            } else {
                callback(new Error(`CORS: origin ${origin} not allowed`));
            }
        },
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With']
    };
    app.use(cors(corsOptions));
    app.use(cookieParser());

    const PORT = Number(process.env.PORT) || 5000;
    app.use('/health', (req, res) => res.status(200).send('OK'));
    app.use('/conversations', conversationsRouter());
    app.use('/experiments', experimentsRouter());
    app.use('/users', usersRouter());
    app.use('/agents', agentsRouter());
    app.use('/dataAggregation', dataAggregationRouter());
    app.use('/forms', formsRouter());

    app.listen(PORT, '0.0.0.0', () => {
        console.log(`Server started on http://0.0.0.0:${PORT}`);
        console.log(`Local access: http://localhost:${PORT}`);
        console.log(`Emulator access: http://10.0.2.2:${PORT}`);
    });
};

if (process.argv[2] === 'create-user') {
    const [, , , username, password] = process.argv;
    createAdminUser(username, password);
} else {
    setupServer();
}
