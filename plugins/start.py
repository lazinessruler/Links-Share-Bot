import asyncio
import base64
import time
from asyncio import Lock
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.errors import FloodWait, UserNotParticipant, UserIsBlocked, InputUserDeactivated
import os
import asyncio
from asyncio import sleep
from asyncio import Lock
import random 

from bot import Bot
from datetime import datetime, timedelta
from config import *
from database.database import *
from plugins.newpost import revoke_invite_after_5_minutes
from helper_func import *

# Create a lock dictionary for each channel to prevent concurrent link generation
channel_locks = defaultdict(asyncio.Lock)

user_banned_until = {}

# Broadcast variables
cancel_lock = asyncio.Lock()
is_canceled = False

# Random image selector for start
START_IMAGES = [
    "https://i.postimg.cc/02hcmLx7/3726acbf3c8d079d88edc7a54e22b1e6.jpg",
    "https://i.postimg.cc/Hsr6rpGy/3ff1f31ba3961d8111817de48aa47670.jpg",
    "https://i.postimg.cc/jdDMDsVP/56932388f91573455119ec6aa27e7cd9.jpg",
    "https://i.postimg.cc/dth5hqMR/c84af4f21fa1c3f4f2e1a056241e430d.jpg",
    "https://i.postimg.cc/rFDfD86V/df23ccf92c7fad0e0d59c1b316e559c9.jpg",
    "https://i.postimg.cc/L6JxJHdP/f881453d3689d3965023c7079a61a9b0.jpg"
]

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Bot, message: Message):
    user_id = message.from_user.id

    if user_id in user_banned_until:
        if datetime.now() < user_banned_until[user_id]:
            return await message.reply_text(
                "<b><blockquote expandable>You are temporarily banned from using commands due to spamming. Try again later.</b>",
                parse_mode=ParseMode.HTML
            )
            
    await add_user(user_id)

   # ✅ Check Force Subscription
    #if not await is_subscribed(client, user_id):
        #await temp.delete()
        #return await not_joined(client, message)

# 
    # Check FSub requirements
   #  fsub_channels = await get_fsub_channels()
   #  if fsub_channels:
    #     is_subscribed, subscription_message, subscription_buttons = await check_subscription_status(client, user_id, fsub_channels)
   #      if not is_subscribed:
    #         return await message.reply_text(
    #             subscription_message,
    #             reply_markup=subscription_buttons,
    #             parse_mode=ParseMode.HTML
     #        )

    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
            is_request = base64_string.startswith("req_")
            
            if is_request:
                base64_string = base64_string[4:]
                channel_id = await get_channel_by_encoded_link2(base64_string)
            else:
                channel_id = await get_channel_by_encoded_link(base64_string)
            
            if not channel_id:
                return await message.reply_text(
                    "<b><blockquote expandable>Invalid or expired invite link.</b>",
                    parse_mode=ParseMode.HTML
                )

            # Check if this is a /genlink link (original_link exists)
            from database.database import get_original_link
            original_link = await get_original_link(channel_id)
            if original_link:
                button = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("• Proceed to Link •", url=original_link)]]
                )
                return await message.reply_text(
                    "<b><blockquote expandable>ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ</b>",
                    reply_markup=button,
                    parse_mode=ParseMode.HTML
                )

            # Use a lock for this channel to prevent concurrent link generation
            async with channel_locks[channel_id]:
                # Check if we already have a valid link
                old_link_info = await get_current_invite_link(channel_id)
                current_time = datetime.now()
                
                # If we have an existing link and it's not expired yet (assuming 5 minutes validity)
                if old_link_info:
                    link_created_time = await get_link_creation_time(channel_id)
                    if link_created_time and (current_time - link_created_time).total_seconds() < 240:  # 4 minutes
                        # Use existing link
                        invite_link = old_link_info["invite_link"]
                        is_request_link = old_link_info["is_request"]
                    else:
                        # Revoke old link and create new one
                        try:
                            await client.revoke_chat_invite_link(channel_id, old_link_info["invite_link"])
                            print(f"Revoked old {'request' if old_link_info['is_request'] else 'invite'} link for channel {channel_id}")
                        except Exception as e:
                            print(f"Failed to revoke old link for channel {channel_id}: {e}")
                        
                        # Create new link
                        invite = await client.create_chat_invite_link(
                            chat_id=channel_id,
                            expire_date=current_time + timedelta(minutes=10),
                            creates_join_request=is_request
                        )
                        invite_link = invite.invite_link
                        is_request_link = is_request
                        await save_invite_link(channel_id, invite_link, is_request_link)
                else:
                    # Create new link
                    invite = await client.create_chat_invite_link(
                        chat_id=channel_id,
                        expire_date=current_time + timedelta(minutes=10),
                        creates_join_request=is_request
                    )
                    invite_link = invite.invite_link
                    is_request_link = is_request
                    await save_invite_link(channel_id, invite_link, is_request_link)

            button_text = "• ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴊᴏɪɴ •" if is_request_link else "• ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ •"
            button = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=invite_link)]])

            wait_msg = await message.reply_text(
                "⏳",
                parse_mode=ParseMode.HTML
            )
            
            await wait_msg.delete()
            
            await message.reply_text(
                "<b><blockquote expandable>ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ</b>",
                reply_markup=button,
                parse_mode=ParseMode.HTML
            )

            note_msg = await message.reply_text(
                "<u><b>Note: If the link is expired, please click the post link again to get a new one.</b></u>",
                parse_mode=ParseMode.HTML
            )

            # Auto-delete the note message after 5 minutes
            asyncio.create_task(delete_after_delay(note_msg, 300))

            asyncio.create_task(revoke_invite_after_5_minutes(client, channel_id, invite_link, is_request_link))

        except Exception as e:
            await message.reply_text(
                "<b><blockquote expandable>Invalid or expired invite link.</b>",
                parse_mode=ParseMode.HTML
            )
            print(f"Decoding error: {e}")
    else:
        # Random image selection from your provided images
        start_image = random.choice(START_IMAGES)
        
        # Improved inline buttons with better design
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
                [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ •", callback_data="about"),
                    InlineKeyboardButton("• ᴄʜᴀɴɴᴇʟ •", url="https://t.me/DragonByte_Network")
                ],
                [InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]
            ]
        )
        
        # Improved start message with better formatting
        CUSTOM_START_MSG = f"""
<b><blockquote expandable>✨ ʏᴜᴛᴀ ꜱʜᴀʀᴇ ʙᴏᴛ ✨</blockquote>

ʜᴇʏ <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> 👋

ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ꜱʜᴀʀɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ.

ʏᴏᴜ ᴄᴀɴ ᴀᴄᴄᴇꜱꜱ ᴛᴡᴏ ᴇxᴄʟᴜꜱɪᴠᴇ ᴄʜᴀɴɴᴇʟꜱ:
» ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ
» ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ

ᴜꜱᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ ʏᴏᴜʀ ᴘʀᴇꜰᴇʀʀᴇᴅ ᴄʜᴀɴɴᴇʟ.

ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ʙʏ <a href='https://t.me/xFlexyy'>` 𝘍𝘭𝘦𝘹𝘺𝘺 𓄼🦅𓄹</a> | <a href='https://t.me/DragonByte_Network'>𝖣𝗋𝖺𝗀𝗈𝗇𝖡𝗒𝗍𝖾 𝖭𝖾𝗍𝗐𝗈𝗋𝗄</a>
</b>"""
        
        # Show waiting emoji and instantly delete it
        wait_msg = await message.reply_text("⏳")
        await asyncio.sleep(0.1)
        await wait_msg.delete()
        
        try:
            await message.reply_photo(
                photo=start_image,
                caption=CUSTOM_START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error sending start picture: {e}")
            await message.reply_text(
                CUSTOM_START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )


#=====================================================================================##
# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport

async def get_link_creation_time(channel_id):
    """Get the creation time of the current invite link for a channel."""
    try:
        from database.database import channels_collection
        channel = await channels_collection.find_one({"channel_id": channel_id, "status": "active"})
        if channel and "invite_link_created_at" in channel:
            return channel["invite_link_created_at"]
        return None
    except Exception as e:
        print(f"Error fetching link creation time for channel {channel_id}: {e}")
        return None

# Create a global dictionary to store chat data
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    #temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()  # Should return list of (chat_id, mode) tuples
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)  # fetch mode 

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    # Cache chat info
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    # Generate proper invite link based on the mode
                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                            )
                        link = invite.invite_link

                    else:
                        if data.username:
                            link = f"https://t.me/{data.username}"
                        else:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None)
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    #await temp.edit(f"<b>{'! ' * count}</b>")

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return #await temp.edit(
                        #f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n"
                        #f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    #)

        # Retry Button
        try:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ])
        except IndexError:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print(f"Final Error: {e}")

@Bot.on_callback_query(filters.regex("close"))
async def close_callback(client: Bot, callback_query):
    await callback_query.answer()
    await callback_query.message.delete()

@Bot.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client: Bot, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    fsub_channels = await get_fsub_channels()
    
    if not fsub_channels:
        await callback_query.message.edit_text(
            "<b>No FSub channels configured!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    is_subscribed, subscription_message, subscription_buttons = await check_subscription_status(client, user_id, fsub_channels)
    if is_subscribed:
        await callback_query.message.edit_text(
            "<b>You are subscribed to all required channels! Use /start to proceed.</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await callback_query.message.edit_text(
            subscription_message,
            reply_markup=subscription_buttons,
            parse_mode=ParseMode.HTML
        )

WAIT_MSG = "<b>Processing...</b>"

REPLY_ERROR = """Usᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴀs ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀɴʏ Tᴇʟᴇɢʀᴀᴍ ᴍᴇssᴀɢᴇ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ sᴘᴀᴄᴇs."""
# Define a global variable to store the cancel state
is_canceled = False
cancel_lock = Lock()

@Bot.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def info(client: Bot, message: Message):   
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• Close •", callback_data="close")]])
    
    start_time = time.time()
    temp_msg = await message.reply("<b><i>Processing...</i></b>", quote=True, parse_mode=ParseMode.HTML)
    end_time = time.time()
    
    ping_time = (end_time - start_time) * 1000
    
    users = await full_userbase()
    now = datetime.now()
    delta = now - client.uptime
    bottime = get_readable_time(delta.seconds)
    
    await temp_msg.edit(
        f"<b>Users: {len(users)}\n\nUptime: {bottime}\n\nPing: {ping_time:.2f} ms</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

#--------------------------------------------------------------[[ADMIN COMMANDS]]---------------------------------------------------------------------------#
# Handler for the /cancel command
@Bot.on_message(filters.command('cancel') & filters.private & is_owner_or_admin)
async def cancel_broadcast(client: Bot, message: Message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True

@Bot.on_message(filters.private & filters.command('broadcast') & is_owner_or_admin)
async def broadcast(client: Bot, message: Message):
    global is_canceled
    args = message.text.split()[1:]

    if not message.reply_to_message:
        msg = await message.reply(
            "Reply to a message to broadcast.\n\nUsage examples:\n"
            "`/broadcast normal`\n"
            "`/broadcast pin`\n"
            "`/broadcast delete 30`\n"
            "`/broadcast pin delete 30`\n"
            "`/broadcast silent`\n"
        )
        await asyncio.sleep(8)
        return await msg.delete()

    # Defaults
    do_pin = False
    do_delete = False
    duration = 0
    silent = False
    mode_text = []

    i = 0
    while i < len(args):
        arg = args[i].lower()
        if arg == "pin":
            do_pin = True
            mode_text.append("PIN")
        elif arg == "delete":
            do_delete = True
            try:
                duration = int(args[i + 1])
                i += 1
            except (IndexError, ValueError):
                return await message.reply("<b>Provide valid duration for delete mode.</b>\nUsage: `/broadcast delete 30`")
            mode_text.append(f"DELETE({duration}s)")
        elif arg == "silent":
            silent = True
            mode_text.append("SILENT")
        else:
            mode_text.append(arg.upper())
        i += 1

    if not mode_text:
        mode_text.append("NORMAL")

    # Reset cancel flag
    async with cancel_lock:
        is_canceled = False

    query = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = len(query)
    successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply(f"<i>Broadcasting in <b>{' + '.join(mode_text)}</b> mode...</i>")

    bar_length = 20
    progress_bar = ''
    last_update_percentage = 0
    update_interval = 0.05  # 5%

    for i, chat_id in enumerate(query, start=1):
        async with cancel_lock:
            if is_canceled:
                await pls_wait.edit(f"›› BROADCAST ({' + '.join(mode_text)}) CANCELED ❌")
                return

        try:
            sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)

            if do_pin:
                await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
            if do_delete:
                asyncio.create_task(auto_delete(sent_msg, duration))

            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)
                if do_pin:
                    await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
                if do_delete:
                    asyncio.create_task(auto_delete(sent_msg, duration))
                successful += 1
            except:
                unsuccessful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except:
            unsuccessful += 1
            await del_user(chat_id)

        # Progress
        percent_complete = i / total
        if percent_complete - last_update_percentage >= update_interval or last_update_percentage == 0:
            num_blocks = int(percent_complete * bar_length)
            progress_bar = "●" * num_blocks + "○" * (bar_length - num_blocks)
            status_update = f"""<b>›› BROADCAST ({' + '.join(mode_text)}) IN PROGRESS...

<blockquote>⏳:</b> [{progress_bar}] <code>{percent_complete:.0%}</code></blockquote>

<b>›› Total Users: <code>{total}</code>
›› Successful: <code>{successful}</code>
›› Blocked: <code>{blocked}</code>
›› Deleted: <code>{deleted}</code>
›› Unsuccessful: <code>{unsuccessful}</code></b>

<i>➪ To stop broadcasting click: <b>/cancel</b></i>"""
            await pls_wait.edit(status_update)
            last_update_percentage = percent_complete

    # Final status
    final_status = f"""<b>›› BROADCAST ({' + '.join(mode_text)}) COMPLETED ✅

<blockquote>Dᴏɴᴇ:</b> [{progress_bar}] {percent_complete:.0%}</blockquote>

<b>›› Total Users: <code>{total}</code>
›› Successful: <code>{successful}</code>
›› Blocked: <code>{blocked}</code>
›› Deleted: <code>{deleted}</code>
›› Unsuccessful: <code>{unsuccessful}</code></b>"""
    return await pls_wait.edit(final_status)


# helper for delete mode
async def auto_delete(sent_msg, duration):
    await asyncio.sleep(duration)
    try:
        await sent_msg.delete()
    except:
        pass


#----------------------------------

user_message_count = {}
user_banned_until = {}

MAX_MESSAGES = 3
TIME_WINDOW = timedelta(seconds=10)
BAN_DURATION = timedelta(hours=1)

"""

@Bot.on_message(filters.private)
async def monitor_messages(client: Bot, message: Message):
    user_id = message.from_user.id
    now = datetime.now()

    if message.text and message.text.startswith("/"):
        return

    if user_id in ADMINS:
        return 

    if user_id in user_banned_until and now < user_banned_until[user_id]:
        await message.reply_text(
            "<b><blockquote expandable>You are temporarily banned from using commands due to spamming. Try again later.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    if user_id not in user_message_count:
        user_message_count[user_id] = []

    user_message_count[user_id].append(now)
    user_message_count[user_id] = [time for time in user_message_count[user_id] if now - time <= TIME_WINDOW]

    if len(user_message_count[user_id]) > MAX_MESSAGES:
        user_banned_until[user_id] = now + BAN_DURATION
        await message.reply_text(
            "<b><blockquote expandable>You are temporarily banned from using commands due to spamming. Try again later.</b>",
            parse_mode=ParseMode.HTML
        )
        return

"""

@Bot.on_callback_query()
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data  
    chat_id = query.message.chat.id
    
    if data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass
    
    elif data == "about":
        user = await client.get_users(OWNER_ID)
        user_link = f"https://t.me/{user.username}" if user.username else f"tg://openmessage?user_id={OWNER_ID}"
        
        # Improved about message with your branding
        CUSTOM_ABOUT_TXT = f"""
<b><blockquote expandable>ℹ️ ᴀʙᴏᴜᴛ ᴛʜᴇ ʙᴏᴛ</blockquote>

<b>ʙᴏᴛ ɴᴀᴍᴇ:</b> <a href='https://t.me/YutaShareBot'>Yᴜᴛᴀ Sʜᴀʀᴇ Bᴏᴛ</a>
<b>ᴅᴇᴠᴇʟᴏᴘᴇʀ:</b> <a href='https://t.me/xFlexyy'>` 𝘍𝘭𝘦𝘹𝘺𝘺 𓄼🦅𓄹</a>
<b>ᴄᴏᴍᴍᴜɴɪᴛʏ:</b> <a href='https://t.me/DragonByte_Network'>𝖣𝗋𝖺𝗀𝗈𝗇𝖡𝗒𝗍𝖾 𝖭𝖾𝗍𝗐𝗈𝗋𝗄</a>

<b>ғᴇᴀᴛᴜʀᴇs:</b>
• Exᴄʟᴜsɪᴠᴇ Aɴɪᴍᴇ Cʜᴀɴɴᴇʟ
• Hᴇɴᴛᴀɪ Cᴏɴᴛᴇɴᴛ Aᴄᴄᴇss
• Fᴀsᴛ & Rᴇʟɪᴀʙʟᴇ Sʜᴀʀɪɴɢ

ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ʙʏ <a href='https://t.me/xFlexyy'>@xFlexyy</a>
</b>"""
        
        await query.edit_message_media(
            InputMediaPhoto(
                random.choice(START_IMAGES),
                CUSTOM_ABOUT_TXT
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('• ʙᴀᴄᴋ', callback_data='start'), InlineKeyboardButton('ᴄʟᴏsᴇ •', callback_data='close')]
            ]),
        )

    elif data == "channels":
        # Improved channels message with direct links
        CHANNELS_BUTTONS = InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
            [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
            [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="start")]
        ])
        
        await query.message.edit_text(
            "<b>📢 sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ:</b>",
            reply_markup=CHANNELS_BUTTONS,
            parse_mode=ParseMode.HTML
        )
        
    elif data in ["start", "home"]:
        # Random image selection
        start_image = random.choice(START_IMAGES)
        
        # Improved inline buttons
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
                [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ •", callback_data="about"),
                    InlineKeyboardButton("• ᴄʜᴀɴɴᴇʟ •", url="https://t.me/DragonByte_Network")
                ],
                [InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]
            ]
        )
        
        # Improved start message
        CUSTOM_START_MSG = f"""
<b><blockquote expandable>✨ ʏᴜᴛᴀ ꜱʜᴀʀᴇ ʙᴏᴛ ✨</blockquote>

ʜᴇʏ <a href='tg://user?id={query.from_user.id}'>{query.from_user.first_name}</a> 👋
ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ꜱʜᴀʀɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ.

ʏᴏᴜ ᴄᴀɴ ᴀᴄᴄᴇꜱꜱ ᴛᴡᴏ ᴇxᴄʟᴜꜱɪᴠᴇ ᴄʜᴀɴɴᴇʟꜱ:
» ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ
» ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ

ᴜꜱᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ ʏᴏᴜʀ ᴘʀᴇꜰᴇʀʀᴇᴅ ᴄʜᴀɴɴᴇʟ.

ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ʙʏ <a href='https://t.me/xFlexyy'>` 𝘍𝘭𝘦𝘹𝘺𝘺 𓄼🦅𓄹</a> | <a href='https://t.me/DragonByte_Network'>𝖣𝗋𝖺𝗀𝗈𝗇𝖡𝗒𝗍𝖾 𝖭𝖾𝗍𝗐𝗈𝗋𝗄</a>
</b>"""
        
        try:
            await query.edit_message_media(
                InputMediaPhoto(
                    start_image,
                    CUSTOM_START_MSG
                ),
                reply_markup=inline_buttons
            )
        except Exception as e:
            print(f"Error sending start/home photo: {e}")
            await query.edit_message_text(
                CUSTOM_START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )


    elif data.startswith("rfs_ch_"):
        cid = int(data.split("_")[2])
        try:
            chat = await client.get_chat(cid)
            mode = await db.get_channel_mode(cid)
            status = "🟢 ᴏɴ" if mode == "on" else "🔴 ᴏғғ"
            new_mode = "ᴏғғ" if mode == "on" else "on"
            buttons = [
                [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
                [InlineKeyboardButton("‹ ʙᴀᴄᴋ", callback_data="fsub_back")]
            ]
            await query.message.edit_text(
                f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await query.answer("Failed to fetch channel info", show_alert=True)

    elif data.startswith("rfs_toggle_"):
        cid, action = data.split("_")[2:]
        cid = int(cid)
        mode = "on" if action == "on" else "off"

        await db.set_channel_mode(cid, mode)
        await query.answer(f"Force-Sub set to {'ON' if mode == 'on' else 'OFF'}")

        # Refresh the same channel's mode view
        chat = await client.get_chat(cid)
        status = "🟢 ON" if mode == "on" else "🔴 OFF"
        new_mode = "off" if mode == "on" else "on"
        buttons = [
            [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
            [InlineKeyboardButton("‹ ʙᴀᴄᴋ", callback_data="fsub_back")]
        ]
        await query.message.edit_text(
            f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "fsub_back":
        channels = await db.show_channels()
        buttons = []
        for cid in channels:
            try:
                chat = await client.get_chat(cid)
                mode = await db.get_channel_mode(cid)
                status = "🟢" if mode == "on" else "🔴"
                buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{cid}")])
            except:
                continue

        await query.message.edit_text(
            "sᴇʟᴇᴄᴛ ᴀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴛᴏɢɢʟᴇ ɪᴛs ғᴏʀᴄᴇ-sᴜʙ ᴍᴏᴅᴇ:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

def delete_after_delay(msg, delay):
    async def inner():
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except:
            pass
    return inner()
