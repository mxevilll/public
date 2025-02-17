const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { PeerServer } = require('peer');
const cors = require('cors');

const app = express();
const server = http.createServer(app);

app.use(cors({
    origin: "*",
    methods: ["GET", "POST"]
}));

const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    },
    path: '/ws'
});

let connectedUsers = {}; // Map userId to { socketId, roomId, role }
let roomDetails = {}; // Map roomId to { streamerId, viewersCount }

io.on('connection', (socket) => {
    console.log(`New connection: ${socket.id}`);

    socket.on('join-room', ({ roomId, userId, role }) => {
        socket.join(roomId);
        connectedUsers[userId] = { socketId: socket.id, roomId, role };
        console.log(`${role === 2 ? 'Streamer' : 'Viewer'} ${userId} joined room ${roomId}`);

        const room = io.sockets.adapter.rooms.get(roomId);
        const viewersCount = room ? room.size - (role === 2 ? 1 : 0) : 0; // Exclude streamer if role === 2
        console.log(`Sending viewers count to room ${roomId}: ${viewersCount}`);
        io.to(roomId).emit('viewers-update', { viewersCount });

        if (role === 2) {
            roomDetails[roomId] = { streamerId: userId, viewersCount };
            console.log(`Streamer setup complete in room ${roomId}`);
            socket.to(roomId).emit('streamer-ready', { streamerId: userId });
        } else {
            if (roomDetails[roomId] && roomDetails[roomId].streamerId) {
                socket.emit('streamer-ready', { streamerId: roomDetails[roomId].streamerId });
            }
        }
    });

    socket.on('send-message', ({ id, name, message, roomId }) => {
        console.log(`Broadcasting message from ${name} to room ${roomId}: ${message}`);
        socket.to(roomId).emit('receive-message', { id, name, message });
    });

    socket.on('payment-made', ({ roomId, amount, userId }) => {
        console.log(`Payment made by user ${userId} in room ${roomId} for amount ${amount}`);
        const halfAmount = amount / 2;
        const room = roomDetails[roomId];
        if (!room) {
            console.error(`No streamer found for room ${roomId}`);
            return;
        }

        const streamerId = room.streamerId;
        const streamer = connectedUsers[streamerId];
        if (streamer) {
            io.to(streamer.socketId).emit('credit-tokens', { amount: halfAmount });
            console.log(`Credited ${halfAmount} tokens to streamer ${streamerId} in room ${roomId}`);
        } else {
            console.error(`Streamer ${streamerId} not connected`);
        }

        // Viewer tokens are handled on client-side (in Firebase), so we don't manage them here

        io.in(roomId).emit('start-timer', { duration: 900 });
        console.log(`Timer started for room ${roomId} with duration 900 seconds`);

        // Emit 'viewer-paid' to streamer to initiate private session
        io.to(streamer.socketId).emit('viewer-paid', { viewerId: userId });
    });

    socket.on('end-all-private-sessions', () => {
        const userEntry = Object.entries(connectedUsers).find(([userId, userInfo]) => userInfo.socketId === socket.id && userInfo.role === 2);
        if (userEntry) {
            const [userId, userInfo] = userEntry;
            const roomId = userInfo.roomId;
            console.log(`Ending all private sessions for streamer ${userId} in room ${roomId}`);
            io.to(roomId).emit('end-private-session');
        }
    });

    socket.on('disconnect', () => {
        console.log(`Socket disconnected: ${socket.id}`);
        const userEntry = Object.entries(connectedUsers).find(([userId, userInfo]) => userInfo.socketId === socket.id);
        if (userEntry) {
            const [userId, userInfo] = userEntry;
            const { roomId, role } = userInfo;
            delete connectedUsers[userId];
            console.log(`User ${userId} (${role === 2 ? 'Streamer' : 'Viewer'}) disconnected from room ${roomId}`);

            const room = io.sockets.adapter.rooms.get(roomId);
            const viewersCount = room ? room.size - (role === 2 ? 1 : 0) : 0;
            io.to(roomId).emit('viewers-update', { viewersCount });

            if (role === 2 && roomDetails[roomId] && roomDetails[roomId].streamerId === userId) {
                delete roomDetails[roomId];
                console.log(`Streamer ${userId} left room ${roomId}, room details cleared`);
                io.to(roomId).emit('streamer-disconnected');
            }
        }
    });
});

const PORT = process.env.PORT || 33302;
server.listen(PORT, () => {
    console.log(`Socket.IO Server running on http://localhost:${PORT}`);
});

const peerServer = PeerServer({ port: 33303, path: '/ws3' });
console.log(`PeerJS Server running on http://localhost:33303`);
