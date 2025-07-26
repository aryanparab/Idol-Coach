import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/route";
import { connectToDatabase } from "../../../../lib/mongodb";

export async function GET(request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.email) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { db } = await connectToDatabase();
    const chats = await db
      .collection("chats")
      .find({ userEmail: session.user.email })
      .sort({ updatedAt: -1 })
      .toArray();

    return NextResponse.json({ chats });
  } catch (error) {
    console.error("Error fetching chats:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.email) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { song, messages, userEmail } = await request.json();

    if (!song || !messages || userEmail !== session.user.email) {
      return NextResponse.json({ error: "Invalid request data" }, { status: 400 });
    }

    const { db } = await connectToDatabase();

    const newChat = {
      song,
      messages,
      userEmail: session.user.email,
      userName: session.user.name,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    const result = await db.collection("chats").insertOne(newChat);
    const chat = await db.collection("chats").findOne({ _id: result.insertedId });

    return NextResponse.json({ chat }, { status: 201 });
  } catch (error) {
    console.error("Error creating chat:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
