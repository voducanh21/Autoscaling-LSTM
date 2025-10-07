// chatdb initialization removed (chat-service deleted)
// db = db.getSiblingDB('chatdb');
// db.createCollection('messages');

db = db.getSiblingDB('orderdb');
db.createCollection('orders');
