import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import deep_linking, executor
from typing import List


class Quiz:
    type: str = 'quiz'

    def __init__(self, quiz_id, question, options, correct_option_id, owner_id):

        self.quiz_id: str = quiz_id
        self.question: str = question
        self.options: List[str] = [*options]
        self.correct_option_id: int = correct_option_id
        self.owner: int = owner_id
        self.winners: List[int] = []
        self.chat_id: int = 0
        self.message_id: int = 0


TOKEN = '5450083383:AAE0uHMDPdB__eGVwnBhGUOoqdeyzARYJRk'
bot = Bot(TOKEN)
dp = Dispatcher(bot=bot)
quizzes_database = {}
quizzes_owners = {}
logging.basicConfig(level=logging.INFO)


@dp.poll_answer_handler()
async def handle_poll_answer(quiz_answer: types.PollAnswer):
    quiz_owner = quizzes_owners.get(quiz_answer.poll_id)
    if not quiz_owner:
        logging.error(f"Не могу найти автора викторины с quiz_answer.poll_id = {quiz_answer.poll_id}")
        return
    for saved_quiz in quizzes_database[quiz_owner]:
        if saved_quiz.quiz_id == quiz_answer.poll_id:
            if saved_quiz.correct_option_id == quiz_answer.option_ids[0]:
                saved_quiz.winners.append(quiz_answer.user.id)
                if len(saved_quiz.winners) == 2:
                    await bot.stop_poll(saved_quiz.chat_id, saved_quiz.message_id)


@dp.poll_handler(lambda active_quiz: active_quiz.is_closed is True)
async def just_poll_answer(active_quiz: types.Poll):
    quiz_owner = quizzes_owners.get(active_quiz.id)
    if not quiz_owner:
        logging.error(f"Не могу найти автора викторины с active_quiz.id = {active_quiz.id}")
        return
    for num, saved_quiz in enumerate(quizzes_database[quiz_owner]):
        if saved_quiz.quiz_id == active_quiz.id:

            congrats_text = []
            for winner in saved_quiz.winners:
                chat_member_info = await bot.get_chat_member(saved_quiz.chat_id, winner)
                congrats_text.append(chat_member_info.user.get_mention(as_html=True))

            await bot.send_message(saved_quiz.chat_id, "Викторина закончена, всем спасибо! Вот наши победители:\n\n"
                                   + "\n".join(congrats_text), parse_mode="HTML")

            del quizzes_owners[active_quiz.id]
            del quizzes_database[quiz_owner][num]


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    if message.chat.type == types.ChatType.PRIVATE:
        poll_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        poll_keyboard.add(types.KeyboardButton(text="Создать викторину",
                                               request_poll=types.KeyboardButtonPollType(type=types.PollType.QUIZ)))
        poll_keyboard.add(types.KeyboardButton(text="Отмена"))
        await message.answer("Нажмите на кнопку ниже и создайте викторину! "
                             "Внимание: в дальнейшем она будет публичной (неанонимной).", reply_markup=poll_keyboard)
    else:
        words = message.text.split()

        if len(words) == 1:
            bot_info = await bot.get_me()
            keyboard = types.InlineKeyboardMarkup()
            move_to_dm_button = types.InlineKeyboardButton(text="Перейти в ЛС",
                                                           url=f"t.me/{bot_info.username}?start=anything")
            keyboard.add(move_to_dm_button)
            await message.reply("Не выбрана ни одна викторина. Пожалуйста, перейдите в личные сообщения с ботом, "
                                "чтобы создать новую.", reply_markup=keyboard)

        else:
            quiz_owner = quizzes_owners.get(words[1])
            if not quiz_owner:
                await message.reply("Викторина удалена, недействительна или уже запущена в другой группе. Попробуйте создать новую.")
                return
            for saved_quiz in quizzes_database[quiz_owner]:
                if saved_quiz.quiz_id == words[1]:
                    msg = await bot.send_poll(chat_id=message.chat.id, question=saved_quiz.question,
                                              is_anonymous=False, options=saved_quiz.options, type="quiz",
                                              correct_option_id=saved_quiz.correct_option_id)
                    quizzes_owners[msg.poll.id] = quiz_owner
                    del quizzes_owners[words[1]]
                    saved_quiz.quiz_id = msg.poll.id
                    saved_quiz.chat_id = msg.chat.id
                    saved_quiz.message_id = msg.message_id


@dp.message_handler(lambda message: message.text == "Отмена")
async def action_cancel(message: types.Message):
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer("Действие отменено. Введите /start, чтобы начать заново.", reply_markup=remove_keyboard)


@dp.message_handler(content_types=["poll"])
async def msg_with_poll(message: types.Message):

    if not quizzes_database.get(str(message.from_user.id)):
        quizzes_database[str(message.from_user.id)] = []

    if message.poll.type != "quiz":
        await message.reply("Извините, я принимаю только викторины (quiz)!")
        return

    quizzes_database[str(message.from_user.id)].append(Quiz(
        quiz_id=message.poll.id,
        question=message.poll.question,
        options=[o.text for o in message.poll.options],
        correct_option_id=message.poll.correct_option_id,
        owner_id=message.from_user.id)
    )

    quizzes_owners[message.poll.id] = str(message.from_user.id)

    await message.reply(
        f"Викторина сохранена. Общее число сохранённых викторин: {len(quizzes_database[str(message.from_user.id)])}")


@dp.inline_handler()
async def inline_query(query: types.InlineQuery):
    results = []
    user_quizzes = quizzes_database.get(str(query.from_user.id))
    if user_quizzes:
        for quiz in user_quizzes:
            keyboard = types.InlineKeyboardMarkup()
            start_quiz_button = types.InlineKeyboardButton(
                text="Отправить в группу",
                url=await deep_linking.get_startgroup_link(quiz.quiz_id)
            )
            keyboard.add(start_quiz_button)
            results.append(types.InlineQueryResultArticle(
                id=quiz.quiz_id,
                title=quiz.question,
                input_message_content=types.InputTextMessageContent(
                    message_text="Нажмите кнопку ниже, чтобы отправить викторину в группу."),
                reply_markup=keyboard
            ))
    await query.answer(switch_pm_text="Создать викторину", switch_pm_parameter="_",
                       results=results, cache_time=120, is_personal=True)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
