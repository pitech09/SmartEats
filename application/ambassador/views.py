from flask import flash, redirect, render_template, session, url_for, current_app
from flask_login import current_user, login_required, logout_user
from sqlalchemy import func

from . import ambassador
from .. import db
from ..models import Ambassador, AmbassadorReferralCommission, Order, User


def _require_ambassador():
    if session.get("user_type") != "ambassador":
        flash("Please sign in as an ambassador to continue.", "warning")
        return False
    return True


@ambassador.route("/dashboard")
@login_required
def dashboard():
    if not _require_ambassador():
        return redirect(url_for("auth.newlogin"))

    invite_link = url_for("auth.register", ref=current_user.referral_code, _external=True)
    flash(f"Invite link for ambassador {current_user.id}: {invite_link}")


    recent_orders = (
        db.session.query(Order)
        .join(User, Order.user_id == User.id)
        .filter(User.referred_by_ambassador_id == current_user.id)
        .order_by(Order.create_at.desc())
        .limit(10)
        .all()
    )

    total_orders = (
        db.session.query(func.count(Order.id))
        .join(User, Order.user_id == User.id)
        .filter(User.referred_by_ambassador_id == current_user.id)
        .scalar()
        or 0
    )
    total_discount = (
        db.session.query(func.coalesce(func.sum(Order.ambassador_discount), 0.0))
        .join(User, Order.user_id == User.id)
        .filter(User.referred_by_ambassador_id == current_user.id)
        .scalar()
        or 0.0
    )
    total_referrals = User.query.filter_by(referred_by_ambassador_id=current_user.id).count()
    referred_users = (
        User.query
        .filter_by(referred_by_ambassador_id=current_user.id)
        .order_by(User.referred_at.desc().nullslast(), User.id.desc())
        .all()
    )
    active_referrals = (
        db.session.query(func.count(func.distinct(AmbassadorReferralCommission.user_id)))
        .filter(AmbassadorReferralCommission.ambassador_id == current_user.id)
        .scalar()
        or 0
    )
    referral_commissions = (
        AmbassadorReferralCommission.query
        .filter_by(ambassador_id=current_user.id)
        .order_by(AmbassadorReferralCommission.created_at.desc())
        .limit(10)
        .all()
    )
    total_referral_earnings = (
        db.session.query(func.coalesce(func.sum(AmbassadorReferralCommission.commission_amount), 0.0))
        .filter(AmbassadorReferralCommission.ambassador_id == current_user.id)
        .scalar()
        or 0.0
    )

    return render_template(
        "ambassador/dashboard.html",
        ambassador=current_user,
        invite_link=invite_link,
        recent_orders=recent_orders,
        total_orders=total_orders,
        total_discount=total_discount,
        total_referrals=total_referrals,
        referred_users=referred_users,
        active_referrals=active_referrals,
        referral_commissions=referral_commissions,
        total_referral_earnings=total_referral_earnings,
        referral_min_amount=current_app.config.get("AMBASSADOR_REFERRAL_MIN_ORDER_AMOUNT", 100.0),
        referral_rate=current_app.config.get("AMBASSADOR_REFERRAL_COMMISSION_RATE", 0.05),
    )


@ambassador.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("ambassador_id", None)
    session.pop("user_type", None)
    session.pop("email", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.newlogin"))
