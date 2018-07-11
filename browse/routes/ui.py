"""Provides the user intefaces for browse."""
from typing import Union

from arxiv import status
from flask import Blueprint, render_template, request, Response, session, \
    redirect, current_app, url_for
from werkzeug.exceptions import InternalServerError, NotFound

from browse.controllers import abs_page, get_institution_from_request
from browse.domain.clickthrough import is_hash_valid

blueprint = Blueprint('browse', __name__, url_prefix='')


@blueprint.before_request
def before_request() -> None:
    """Get instituional affiliation from session."""
    if 'institution' not in session:
        institution = get_institution_from_request()
        session['institution'] = institution


@blueprint.after_request
def apply_response_headers(response: Response) -> Response:
    """Prevent UI redress attacks."""
    """Hook for applying response headers to all responses."""
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@blueprint.route('/abs', methods=['GET'])
def bare_abs():
    """Return 404."""
    raise NotFound


@blueprint.route('/abs/', methods=['GET'], defaults={'arxiv_id': ''})
@blueprint.route('/abs/<path:arxiv_id>', methods=['GET', 'POST'])
def abstract(arxiv_id: str) -> Union[str, Response]:
    """Abstract (abs) page view."""
    download_format_pref = request.cookies.get('xxx-ps-defaults')
    response, code, headers = abs_page.get_abs_page(arxiv_id,
                                                    request.args,
                                                    download_format_pref)

    if code == status.HTTP_200_OK:
        return render_template('abs/abs.html', **response), code, headers
    elif code == status.HTTP_301_MOVED_PERMANENTLY:
        return redirect(headers['Location'], code=code)

    raise InternalServerError('Unexpected error')


@blueprint.route('/trackback/', methods=['GET'], defaults={'arxiv_id': ''})
@blueprint.route('/trackback/<path:arxiv_id>', methods=['GET', 'POST'])
def trackback(arxiv_id: str) -> Union[str, Response]:
    """Route to define new trackbacks for papers."""
    # TODO implement
    raise NotFound


@blueprint.route('/ct')
def clickthrough():
    """Controller to log clickthrough to bookmarking sites."""
    if 'url' in request.args and 'v' in request.args \
            and is_hash_valid(current_app.config['SECRET_KEY'], request.args.get('url'), request.args.get('v')):
        return redirect(request.args.get('url'))
    else:
        raise NotFound()
