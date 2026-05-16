# ... (yuqoridagi importlar o'zgarishsiz) ...

# Yangi state
WAITING_SITE_SELECT = 3

# ========== SAYT TANLASH ==========

async def select_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sayt tanlash"""
    query = update.callback_query
    await query.answer()
    
    lang = get_user_lang(query.from_user.id)
    
    if not SITES:
        await query.edit_message_text(
            "❌ Saytlar ro'yxati bo'sh. Admin bilan bog'laning.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]
            ])
        )
        return
    
    keyboard = []
    for i, site in enumerate(SITES):
        keyboard.append([InlineKeyboardButton(
            f"🌐 {site['name']}", 
            callback_data=f'site_{i}'
        )])
    
    keyboard.append([InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')])
    
    await query.edit_message_text(
        get_text(lang, "select_site"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def site_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sayt tanlandi"""
    query = update.callback_query
    await query.answer()
    
    site_index = int(query.data.split('_')[1])
    context.user_data['selected_site'] = site_index
    lang = get_user_lang(query.from_user.id)
    
    site = get_site_by_index(site_index)
    site_name = site['name'] if site else "Noma'lum"
    
    await query.edit_message_text(
        f"🌐 {site_name} tanlandi!\n\n" + get_text(lang, "enter_order_number"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_button(lang, "back"), callback_data='select_site')]
        ])
    )
    
    context.user_data['state'] = WAITING_ORDER_NUMBER

# ========== TO'LOV TASDIQLASH (YANGILANDI) ==========

async def payment_confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov tasdiqlash — avval sayt tanlash"""
    query = update.callback_query
    await query.answer()
    
    await select_site(update, context)

async def process_order_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma raqami — tanlangan saytga qarab tekshiradi"""
    if context.user_data.get('state') != WAITING_ORDER_NUMBER:
        return
    
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    order_number = update.message.text.strip()
    site_index = context.user_data.get('selected_site', 0)
    
    # Tanlangan sayt bilan tekshirish
    payment_service = PaymentService(site_index)
    order_data = await payment_service.check_order(order_number)
    
    if not order_data['found']:
        await update.message.reply_text(
            get_text(lang, "order_not_found"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_button(lang, "back"), callback_data='select_site')]
            ])
        )
        context.user_data['state'] = None
        return
    
    context.user_data['order_number'] = order_number
    context.user_data['order_amount'] = order_data['amount']
    context.user_data['site_index'] = site_index
    context.user_data['site_name'] = order_data.get('site_name', 'Noma\'lum')
    
    text = get_text(lang, "order_found",
                   amount=f"{order_data['amount']:,.0f}",
                   status=order_data['status'])
    
    await update.message.reply_text(text)
    
    # To'lovni bazaga qo'shish (site_index bilan)
    payment_id = db.add_payment(
        user_id, 
        site_index, 
        order_data.get('site_name', ''),
        order_number, 
        order_data['amount']
    )
    context.user_data['payment_id'] = payment_id
    
    await update.message.reply_text(
        "📸 Iltimos, to'lov chekining screen shotini yuboring:\n\n"
        "💡 Bot avtomatik tekshiradi:\n"
        "   ✅ Rasm haqiqiyligi\n"
        "   ✅ Summa to'g'riligi\n"
        "   ✅ Vaqt belgisi\n"
        "   ✅ Tranzaksiya ID"
    )
    
    context.user_data['state'] = WAITING_SCREENSHOT

async def process_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screen shot — avto tekshirish + site ma'lumotlari"""
    if context.user_data.get('state') != WAITING_SCREENSHOT:
        return
    
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    payment_id = context.user_data.get('payment_id')
    order_number = context.user_data.get('order_number')
    order_amount = context.user_data.get('order_amount')
    site_index = context.user_data.get('site_index', 0)
    site_name = context.user_data.get('site_name', 'Noma\'lum')
    
    if not payment_id:
        return
    
    # File olish
    file_id = None
    file_type = None
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = 'document'
    else:
        await update.message.reply_text("❌ Iltimos, rasm yuboring.")
        return
    
    db.update_payment_screenshot(payment_id, file_id, update.message.message_id)
    await update.message.reply_text("🔍 Screen shot avtomatik tekshirilmoqda...")
    
    try:
        file = await context.bot.get_file(file_id)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        check_result = await screenshot_checker.check_screenshot(
            tmp_path, 
            expected_amount=order_amount,
            order_number=order_number
        )
        
        os.unlink(tmp_path)
        
        # Natija (site nomi bilan)
        status_text = f"""📊 Tekshirish natijasi:

🌐 Sayt: {site_name}
🎯 Ishonch darajasi: {check_result['confidence']*100:.0f}%
{"✅ Haqiqiy" if check_result['is_valid'] else "⚠️ Shubhali"}

📋 Topilgan ma'lumotlar:
💰 Summa: {check_result['extracted_data'].get('found_amount', 'N/A')}
🕐 Vaqt: {check_result['extracted_data'].get('found_time', 'N/A')}
🆔 Tranzaksiya ID: {check_result['extracted_data'].get('transaction_id', 'N/A')}

{"✅ Avtomatik tasdiqlandi!" if check_result['is_valid'] else check_result['recommendation']}"""
        
        if check_result['issues']:
            status_text += "\n\n⚠️ Muammolar:\n"
            for issue in check_result['issues']:
                status_text += f"   • {issue}\n"
        
        await update.message.reply_text(status_text)
        
        # AVTO TASDIQLASH
        if check_result['is_valid'] and check_result['confidence'] >= AUTO_APPROVE_THRESHOLD:
            db.approve_payment(payment_id, 0)
            
            # Tanlangan sayt bilan tasdiqlash
            ps = PaymentService(site_index)
            await ps.confirm_payment(order_number)
            
            await update.message.reply_text(
                f"🎉 To'lovingiz avtomatik tasdiqlandi!\n\n"
                f"🌐 Sayt: {site_name}\n"
                f"📋 Buyurtma: #{order_number}\n"
                f"💰 Summa: {order_amount:,.0f} so'm\n\n"
                f"✅ Endi saytdan davom etishingiz mumkin."
            )
            
            # Guruhga xabar (site bilan)
            if PAYMENT_GROUP_ID:
                user = update.effective_user
                await context.bot.send_message(
                    chat_id=PAYMENT_GROUP_ID,
                    text=f"""✅ AVTO TASDIQLANDI!

🌐 Sayt: {site_name}
👤 Foydalanuvchi: {user.first_name} (@{user.username or 'Noma\'lum'})
🆔 ID: {user.id}
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm
🎯 Ishonch: {check_result['confidence']*100:.0f}%
🤖 Avtomatik tasdiq"""
                )
        else:
            # Admin tekshiruviga yuborish (site bilan)
            await update.message.reply_text(
                "⏳ Screen shot admin tekshiruviga yuborildi.\n"
                "Natijasi tez orada xabar qilinadi."
            )
            
            if PAYMENT_GROUP_ID:
                user = update.effective_user
                
                group_text = f"""⚠️ TEKSHIRUV TALAB ETILADI!

🌐 Sayt: {site_name}
👤 Foydalanuvchi: {user.first_name} (@{user.username or 'Noma\'lum'})
🆔 ID: {user.id}
📋 Buyurtma: #{order_number}
💰 Summa: {order_amount:,.0f} so'm
⏰ Vaqt: {update.message.date.strftime('%d.%m.%Y %H:%M')}
🎯 Ishonch: {check_result['confidence']*100:.0f}%

📋 Tekshirish natijalari:
💰 Topilgan summa: {check_result['extracted_data'].get('found_amount', 'N/A')}
🕐 Topilgan vaqt: {check_result['extracted_data'].get('found_time', 'N/A')}
🆔 Tranzaksiya ID: {check_result['extracted_data'].get('transaction_id', 'N/A')}

⚠️ Muammolar:
{chr(10).join(check_result['issues']) if check_result['issues'] else 'Yo\'q'}"""
                
                if file_type == 'photo':
                    group_message = await context.bot.send_photo(
                        chat_id=PAYMENT_GROUP_ID,
                        photo=file_id,
                        caption=group_text
                    )
                else:
                    group_message = await context.bot.send_document(
                        chat_id=PAYMENT_GROUP_ID,
                        document=file_id,
                        caption=group_text
                    )
                
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f'approve_{payment_id}'),
                        InlineKeyboardButton("❌ Rad etish", callback_data=f'reject_{payment_id}')
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=PAYMENT_GROUP_ID,
                    text=f"Sayt: {site_name}\nTo'lovni tasdiqlaysizmi?",
                    reply_markup=confirm_keyboard
                )
                
                db.update_payment_group_message(payment_id, group_message.message_id)
    
    except Exception as e:
        logger.error(f"Avto tekshiruvda xato: {e}")
        await update.message.reply_text(
            "⚠️ Avtomatik tekshirishda xato. Admin tekshiruviga yuborildi."
        )
    
    context.user_data['state'] = None

# ========== TO'LOVLAR TARIXI (YANGILANDI) ==========

async def payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovlar tarixi — sayt nomi bilan"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    
    payments = db.get_user_payments(user_id)
    
    if not payments:
        text = get_text(lang, "no_history")
    else:
        text = "📋 To'lovlar tarixi:\n\n"
        for payment in payments:
            status = "✅ Tasdiqlandi" if payment['status'] == 'approved' else \
                     "⏳ Kutilmoqda" if payment['status'] == 'pending' else "❌ Rad etildi"
            auto = "🤖 Avto" if payment.get('approved_by') == 0 else "👤 Admin"
            site = payment.get('site_name', 'Noma\'lum')
            text += f"🌐 {site}\n"
            text += f"📋 #{payment['order_number']} - {payment['amount']:,.0f} so'm\n"
            text += f"   📅 {payment['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            text += f"   📊 {status} ({auto})\n\n"
    
    keyboard = [[InlineKeyboardButton(get_button(lang, "back"), callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== ASOSIY MENYU (YANGILANDI) ==========

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy menyuga qaytish — sayt tanlash tugmasi bilan"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = get_user_lang(user.id)
    
    welcome_text, welcome_links = db.get_welcome_data()
    text = welcome_text.format(name=user.first_name)
    
    keyboard = []
    for link in welcome_links:
        keyboard.append([InlineKeyboardButton(link['name'], url=link['url'])])
    
    keyboard.extend([
        [InlineKeyboardButton(get_button(lang, "payment_confirm"), callback_data='payment_confirm')],
        [InlineKeyboardButton(get_button(lang, "about_me"), callback_data='about_me'),
         InlineKeyboardButton(get_button(lang, "payment_history"), callback_data='payment_history')],
        [InlineKeyboardButton(get_button(lang, "settings"), callback_data='settings'),
         InlineKeyboardButton(get_button(lang, "about_bot"), callback_data='about_bot')],
        [InlineKeyboardButton(get_button(lang, "questions"), callback_data='questions')]
    ])
    
    if await is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🔧 Admin panel", callback_data='admin_panel')])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ========== HANDLERLAR (YANGILANDI) ==========

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Sayt tanlash
    application.add_handler(CallbackQueryHandler(select_site, pattern='^select_site$'))
    application.add_handler(CallbackQueryHandler(site_selected, pattern='^site_'))
    
    # Asosiy
    application.add_handler(CallbackQueryHandler(payment_confirm_start, pattern='^payment_confirm$'))
    application.add_handler(CallbackQueryHandler(about_me, pattern='^about_me$'))
    application.add_handler(CallbackQueryHandler(payment_history, pattern='^payment_history$'))
    application.add_handler(CallbackQueryHandler(settings, pattern='^settings$'))
    application.add_handler(CallbackQueryHandler(change_language, pattern='^change_language$'))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(about_bot, pattern='^about_bot$'))
    application.add_handler(CallbackQueryHandler(questions, pattern='^questions$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_main$'))
    
    # Admin
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$'))
    application.add_handler(CallbackQueryHandler(admin_report, pattern='^admin_report$'))
    application.add_handler(CallbackQueryHandler(admin_daily_report, pattern='^report_daily$'))
    application.add_handler(CallbackQueryHandler(admin_weekly_report, pattern='^report_weekly$'))
    application.add_handler(CallbackQueryHandler(admin_set_welcome_start, pattern='^admin_set_welcome$'))
    application.add_handler(CallbackQueryHandler(admin_set_questions_start, pattern='^admin_set_questions$'))
    application.add_handler(CallbackQueryHandler(admin_set_about_start, pattern='^admin_set_about$'))
    
    # Tasdiqlash/rad etish
    application.add_handler(CallbackQueryHandler(approve_payment, pattern='^approve_'))
    application.add_handler(CallbackQueryHandler(reject_payment, pattern='^reject_'))
    
    # Xabarlar
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))
    
    print("🤖 Bot ishga tushdi...")
    print("🔍 Avtomatik screen shot tekshiruvi yoqildi!")
    print(f"🌐 Saytlar soni: {len(SITES)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
