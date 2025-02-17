import discord
import discord.ext.commands as commands

import bot.extensions as ext
from bot.clem_bot import ClemBot
from bot.consts import Claims, Colors, DesignatedChannels, Moderation
from bot.messaging.events import Events
from bot.utils.logging_utils import get_logger

log = get_logger(__name__)


class BanCog(commands.Cog):
    def __init__(self, bot: ClemBot):
        self.bot = bot

    @ext.command()
    @ext.long_help(
        "Bans a user from a server and tracks that ban as an infraction, "
        "Optionally allows to specify the number of days from which to purge the "
        "banned users messages"
    )
    @ext.short_help("Bans a user")
    @ext.example(
        (
            "ban @SomeUser Troll",
            "ban 123456789 Another troll",
            "ban @SomeOtherUser 3 Spamming messages",
        )
    )
    @ext.required_claims(Claims.moderation_ban)
    async def ban(
        self,
        ctx: ext.ClemBotCtx,
        subject: discord.Member,
        purge_days: int = 0,
        *,
        reason: str,
    ) -> None:

        if reason and len(reason) > Moderation.max_reason_length:
            embed = discord.Embed(title="Error", color=Colors.Error)
            embed.add_field(
                name="Reason",
                value=f"Reason length is greater than max {Moderation.max_reason_length} characters.",
            )
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
            return

        if ctx.author.roles[-1].position <= subject.roles[-1].position:
            embed = discord.Embed(color=Colors.Error)
            embed.title = "Error: Invalid Permissions"
            embed.add_field(
                name="Reason", value="Cannot moderate someone with the same rank or higher"
            )
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
            return

        if not 0 <= purge_days <= 7:
            embed = discord.Embed(color=Colors.Error)
            embed.title = "Error: Invalid Purge Dates"
            embed.add_field(name="Reason", value="Message purge days must be between 0 and 7")
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
            return

        # Dm the user who was banned
        embed = discord.Embed(color=Colors.ClemsonOrange)
        embed.title = f"You have been banned from Guild {ctx.guild.name}  :hammer:"
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)

        if ctx.guild.icon:
            embed.set_thumbnail(url=str(ctx.guild.icon.url))

        embed.add_field(name="Reason :page_facing_up:", value=f"```{reason}```", inline=False)
        embed.description = f"**Guild:** {ctx.guild.name}"

        try:
            await subject.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            embed = discord.Embed(color=Colors.ClemsonOrange)
            embed.title = f"Dm Ban to {subject} forbidden"
            await self.bot.messenger.publish(
                Events.on_send_in_designated_channel,
                DesignatedChannels.moderation_log,
                ctx.guild.id,
                embed,
            )

        # Ban AFTER dming the user, that way we know that we still share a guild with them
        await self.bot.messenger.publish(
            Events.on_bot_ban,
            guild=ctx.guild,
            author=ctx.author,
            subject=subject,
            reason=reason,
            purge_days=purge_days,
        )

        embed = discord.Embed(color=Colors.ClemsonOrange)
        embed.title = f"{subject} Banned  :hammer:"
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=subject.display_avatar.url)
        embed.description = reason

        await ctx.send(embed=embed)

        embed = discord.Embed(color=Colors.ClemsonOrange)
        embed.title = "Guild Member Banned  :hammer:"
        embed.set_author(
            name=f"{ctx.author}\nId: {ctx.author.id}", icon_url=ctx.author.display_avatar.url
        )
        embed.add_field(name=str(subject), value=f"Id: {subject.id}")
        embed.add_field(name="Reason :page_facing_up:", value=f"```{reason}```", inline=False)
        embed.add_field(name="Message Link  :rocket:", value=f"[Link]({ctx.message.jump_url})")
        if purge_days != 0:
            embed.add_field(
                name="Messages Purged :no_entry_sign:",
                value=f'{purge_days} day{"s" if not purge_days == 1 else ""} of messages purged',
            )
        embed.set_thumbnail(url=subject.display_avatar.url)

        await self.bot.messenger.publish(
            Events.on_send_in_designated_channel,
            DesignatedChannels.moderation_log,
            ctx.guild.id,
            embed,
        )


async def setup(bot: ClemBot) -> None:
    await bot.add_cog(BanCog(bot))
