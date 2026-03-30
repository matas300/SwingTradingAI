const admin = require("firebase-admin");

function firebaseConfig() {
  const raw = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (!raw) {
    throw new Error("Missing FIREBASE_SERVICE_ACCOUNT_JSON");
  }
  const parsed = JSON.parse(raw);
  return {
    credential: admin.credential.cert(parsed),
    projectId: process.env.FIREBASE_PROJECT_ID || parsed.project_id,
  };
}

function firestore() {
  if (!admin.apps.length) {
    admin.initializeApp(firebaseConfig());
  }
  return admin.firestore();
}

module.exports = {
  firestore,
};
