import dataclasses
import math
import typing as t
import uuid

import discord

from bot.clem_bot import ClemBot
from bot.consts import Colors, DesignatedChannels, DiscordLimits
from bot.messaging.events import Events
from bot.services.base_service import BaseService
from bot.utils.helpers import chunk_sequence
from bot.utils.logging_utils import get_logger

log = get_logger(__name__)

# minimum reactions required to get on the starboard
# TODO: implement to where user-editable
MIN_REACTIONS = 4

# dictionary of rankings
RANKINGS = {
    0: "⭐ POPULAR",
    1: "🌟 QUALITY",
    2: "🥉 *THE PEOPLE HAVE SPOKEN*",
    3: "🥈 *INCREDIBLE*",
    4: "🥇 **LEGENDARY**",
    5: "🏆 ***GOD-TIER***",
}


@dataclasses.dataclass
class StarboardPost:
    star_posts: list[discord.Message]
    star_num: int
    star_users: set[discord.User] = dataclasses.field(default_factory=set)


class StarboardService(BaseService):
    def __init__(self, *, bot: ClemBot):
        super().__init__(bot)
        self.curr_posts: dict[int, StarboardPost] = {}
        self.call_back_ids: dict[uuid.UUID, int] = {}

    # function to check to see if a reaction is legal
    def update_check(self, user: discord.User, reaction: discord.Reaction) -> bool:

        # emote verification - stars only
        if str(reaction) != "⭐":
            return False

        # orignal poster reactions don't count
        if reaction.message.author == user:
            return False

        # bot messages don't count
        if reaction.message.author == self.bot.user:
            return False

        # minimum reactions
        if reaction.count < MIN_REACTIONS:
            return False

        return True

    # message formatting function
    def make_star_post(self, message: discord.Message, stars: int) -> discord.Embed:

        title = f'{RANKINGS.get(math.floor((stars - MIN_REACTIONS) / MIN_REACTIONS), 5)} | {stars} Star{"s" if stars > 1 else ""}'

        assert isinstance(message.channel, (discord.TextChannel, discord.Thread))

        embed = discord.Embed(
            title=title,
            color=Colors.ClemsonOrange,
            description=f"_Posted in {message.channel.mention}_ by {message.author.mention}",
        )

        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f'Sent on {message.created_at.strftime("%m/%d/%Y")}')

        if len(message.content) > 0:
            for i, chunk in enumerate(
                chunk_sequence(message.content, DiscordLimits.EmbedFieldLength)
            ):
                embed.add_field(name="Message" if i < 1 else "Continued", value=chunk, inline=False)

        if len(message.attachments) > 0:
            embed.set_image(url=message.attachments[0].url)

        embed.add_field(name="Link", value=f"[Click Me!]({message.jump_url})")
        return embed

    # function to add an entry from the starboard
    async def add_to_starboard(self, user: discord.User, reaction: discord.Reaction) -> None:

        # create message to send in the starboards
        starboard_message = self.make_star_post(reaction.message, reaction.count)
        self.curr_posts[reaction.message.id] = StarboardPost([], reaction.count)
        self.curr_posts[reaction.message.id].star_users.add(user)

        # create unique callback id
        callback_id = uuid.uuid4()
        self.call_back_ids[callback_id] = reaction.message.id

        assert reaction.message.guild is not None

        # send the message to #starboard
        await self.bot.messenger.publish(
            Events.on_send_in_designated_channel,
            DesignatedChannels.starboard,
            reaction.message.guild.id,
            starboard_message,
            callback_id,
        )

    @BaseService.listener(Events.on_designated_message_sent)
    async def get_starboard_post(self, dc_id: uuid.UUID, messages: list[discord.Message]) -> None:
        if dc_id in self.call_back_ids:
            star_message_id = self.call_back_ids[dc_id]

            self.curr_posts[star_message_id].star_posts = messages
            del self.call_back_ids[dc_id]

    async def update_starboard_entry(self, user: discord.User, reaction: discord.Reaction) -> None:
        msg = reaction.message
        curr_post = self.curr_posts[msg.id]

        # if the user has already reacted to this post return so we dont count it twice
        if user in curr_post.star_users:
            return

        # add the user and increment the stars
        curr_post.star_users.add(user)
        curr_post.star_num += 1

        # create the new embed and loop over all the starboard posts
        edit = self.make_star_post(msg, curr_post.star_num)
        for post in curr_post.star_posts:
            await post.edit(embed=edit)

    @BaseService.listener(Events.on_reaction_add)
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        # check to see if the message is worthy
        if self.update_check(user, reaction):
            if reaction.message.id not in self.curr_posts:
                await self.add_to_starboard(user, reaction)
            else:
                await self.update_starboard_entry(user, reaction)

    async def load_service(self) -> None:
        pass
