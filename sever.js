import express from "express";
import { createServer } from "http";
import { Server } from "socket.io";

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer);

const port = 3000;

// Store connected users
const users = new Map();

io.on("connection", (socket) => {
  console.log("A user connected");

  socket.on("register", (username) => {
    users.set(socket.id, username);
    io.emit("userList", Array.from(users.values()));
  });

  socket.on("landmarks", (data) => {
    if (data.targetUser) {
      const targetSocket = Array.from(users.entries()).find(
        ([_, user]) => user === data.targetUser
      );
      if (targetSocket) {
        io.to(targetSocket[0]).emit("landmarks", {
          sender: users.get(socket.id),
          landmarks: data.landmarks,
        });
      }
    }
  });

  socket.on("disconnect", () => {
    users.delete(socket.id);
    io.emit("userList", Array.from(users.values()));
    console.log("A user disconnected");
  });
});

httpServer.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
