db.createUser(
    {
        user: "flaskuser",
        pwd: "xander21",
        roles: [
            {
                role: "readWrite",
                db: "flaskdb"
            }
        ]
    }
);
