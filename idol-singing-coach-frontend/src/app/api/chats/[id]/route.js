// app/api/chats/[id]/route.js
import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '../../auth/[...nextauth]/route'
import { connectToDatabase } from '../../../../../lib/mongodb'
import { ObjectId } from 'mongodb'

export async function GET(request, { params }) {
    try {
        const session = await getServerSession(authOptions)

        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const { id } = params
        if (!ObjectId.isValid(id)) {
            return NextResponse.json({ error: 'Invalid chat ID' }, { status: 400 })
        }

        const { db } = await connectToDatabase()
        
        const chat = await db.collection('chats').findOne({
            _id: new ObjectId(id),
            userEmail: session.user.email
        })

        if (!chat) {
            return NextResponse.json({ error: 'Chat not found' }, { status: 404 })
        }

        return NextResponse.json({ chat })
    } catch (error) {
        console.error('Error fetching chat:', error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}

export async function PUT(request, { params }) {
    try {
        const session = await getServerSession(authOptions)
    
        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const { id } = params // FIX: This was missing!
        const { song, messages, userEmail } = await request.json()

        if (!ObjectId.isValid(id)) {
            return NextResponse.json({ error: 'Invalid chat ID' }, { status: 400 })
        }

        if (!song || !messages || userEmail !== session.user.email) {
            return NextResponse.json({ error: 'Invalid request data' }, { status: 400 })
        }

        const { db } = await connectToDatabase()
        
        const result = await db.collection('chats').updateOne(
            {
                _id: new ObjectId(id),
                userEmail: session.user.email
            },
            {
                $set: {
                    song,
                    messages,
                    updatedAt: new Date()
                }
            }
        )

        if (result.matchedCount === 0) {
            return NextResponse.json({ error: 'Chat not found' }, { status: 404 })
        }

        const updatedChat = await db.collection('chats').findOne({ _id: new ObjectId(id) })
        return NextResponse.json({ chat: updatedChat })

    } catch (error) {
        console.error('Error updating chat:', error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}

export async function DELETE(request, { params }) {
    try {
        const session = await getServerSession(authOptions)
        
        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const { id } = params

        if (!ObjectId.isValid(id)) {
            return NextResponse.json({ error: 'Invalid chat ID' }, { status: 400 })
        }

        const { db } = await connectToDatabase()
        
        const result = await db.collection('chats').deleteOne({
            _id: new ObjectId(id),
            userEmail: session.user.email
        })

        if (result.deletedCount === 0) {
            return NextResponse.json({ error: 'Chat not found' }, { status: 404 })
        }

        return NextResponse.json({ message: 'Chat deleted successfully' })
    } catch (error) {
        console.error('Error deleting chat:', error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}